"""
faithfulness_monitor.py — Lightweight Background Faithfulness Scoring
=====================================================================
Runs AFTER the response is sent to the user (zero latency impact).
Samples 1-in-N queries and scores faithfulness asynchronously.

Architecture:
  User asks question → RAG answers → Response sent to user ✅
                                         ↓ (AFTER response)
                                    Background: enqueue for scoring
                                         ↓ (async worker)
                                    GPT-4o-mini judges faithfulness
                                         ↓
                                    Score saved to Supabase

Dashboard can then show:
  - Average faithfulness over time
  - Questions with low faithfulness (needs attention)
  - Trend charts (is quality improving or degrading?)
"""

import asyncio
import json
import logging
import os
import random
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

SAMPLE_RATE = float(os.getenv("FAITHFULNESS_SAMPLE_RATE", "0.1"))  # 10% of queries
MAX_QUEUE_SIZE = 100  # Don't let the queue grow unbounded
JUDGE_MODEL = os.getenv("FAITHFULNESS_JUDGE_MODEL", "gpt-4o-mini")
SCORE_THRESHOLD_WARN = 0.5  # Log warning if score is below this
ENABLED = os.getenv("FAITHFULNESS_MONITOR_ENABLED", "true").lower() == "true"

# ── In-memory queue (lightweight, no Redis needed) ───────────────────────────

_eval_queue: deque = deque(maxlen=MAX_QUEUE_SIZE)
_worker_task: Optional[asyncio.Task] = None
_stats = {
    "total_sampled": 0,
    "total_scored": 0,
    "total_skipped": 0,
    "avg_score": 0.0,
    "min_score": 1.0,
    "max_score": 0.0,
    "scores": [],  # Rolling window of last 100 scores
}


# ── Public API: Called from main.py after response is sent ───────────────────

def maybe_enqueue(
    question: str,
    answer: str,
    context_chunks: List[str],
    user_id: str,
    doc_name: Optional[str] = None,
    response_time_ms: Optional[float] = None,
):
    """
    Probabilistically enqueue a query for faithfulness scoring.
    Called AFTER the response is sent — zero latency impact.
    """
    if not ENABLED:
        return

    # Sample at configured rate
    if random.random() > SAMPLE_RATE:
        _stats["total_skipped"] += 1
        return

    if len(answer.strip()) < 20:
        return  # Skip trivially short answers

    _stats["total_sampled"] += 1

    _eval_queue.append({
        "question": question,
        "answer": answer,
        "context_chunks": context_chunks[:5],  # Limit to top 5 chunks
        "user_id": user_id,
        "doc_name": doc_name,
        "response_time_ms": response_time_ms,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.debug(f"📊 Faithfulness check enqueued (queue={len(_eval_queue)})")


def get_stats() -> Dict[str, Any]:
    """Return current monitoring stats for the admin dashboard."""
    recent_scores = _stats["scores"][-100:]  # Last 100
    return {
        "enabled": ENABLED,
        "sample_rate": SAMPLE_RATE,
        "queue_size": len(_eval_queue),
        "total_sampled": _stats["total_sampled"],
        "total_scored": _stats["total_scored"],
        "total_skipped": _stats["total_skipped"],
        "avg_score": round(sum(recent_scores) / len(recent_scores), 3) if recent_scores else None,
        "min_score": min(recent_scores) if recent_scores else None,
        "max_score": max(recent_scores) if recent_scores else None,
        "recent_count": len(recent_scores),
    }


# ── Background Worker ────────────────────────────────────────────────────────

async def _score_faithfulness_llm(question: str, answer: str, chunks: List[str]) -> Dict:
    """Use GPT-4o-mini to score faithfulness. Runs in background."""
    import openai

    context_text = "\n---\n".join(chunks)

    prompt = f"""Score the FAITHFULNESS of this RAG answer. Check if every factual claim is supported by the provided context chunks.

QUESTION: {question}

CONTEXT CHUNKS:
{context_text}

ANSWER: {answer}

Return ONLY valid JSON:
{{"score": <float 0.0-1.0>, "supported": <int>, "unsupported": <int>, "hallucinated": <bool>, "reason": "<brief>"}}

Scoring guide:
- 1.0 = Every claim directly supported by context
- 0.7 = Most claims supported, minor unsupported details  
- 0.5 = Mix of supported and unsupported claims
- 0.3 = Mostly unsupported by context
- 0.0 = Answer contradicts or ignores context entirely"""

    try:
        client = openai.AsyncOpenAI()
        response = await client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": "You are a precise RAG evaluation judge. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=200,
        )

        raw = response.choices[0].message.content.strip()
        # Handle markdown code blocks
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        return result
    except json.JSONDecodeError:
        logger.warning(f"Faithfulness judge returned invalid JSON: {raw[:200]}")
        return {"score": -1, "reason": "JSON parse error"}
    except Exception as e:
        logger.warning(f"Faithfulness scoring failed: {e}")
        return {"score": -1, "reason": str(e)}


async def _save_score_to_db(entry: Dict, result: Dict):
    """Save faithfulness score to Supabase for trend analysis."""
    try:
        from database import supabase
        supabase.table("faithfulness_scores").insert({
            "user_id": entry["user_id"],
            "question": entry["question"][:500],  # Truncate for DB
            "answer_preview": entry["answer"][:300],
            "score": result.get("score", -1),
            "supported_claims": result.get("supported", 0),
            "unsupported_claims": result.get("unsupported", 0),
            "hallucinated": result.get("hallucinated", False),
            "reason": result.get("reason", "")[:500],
            "doc_name": entry.get("doc_name"),
            "response_time_ms": entry.get("response_time_ms"),
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        # Table might not exist yet — that's OK, just log
        logger.debug(f"Could not save faithfulness score to DB: {e}")


async def _worker_loop():
    """Background worker that processes the evaluation queue."""
    logger.info("📊 Faithfulness monitor worker started")

    while True:
        if not _eval_queue:
            await asyncio.sleep(5)  # Check every 5 seconds
            continue

        entry = _eval_queue.popleft()

        try:
            result = await _score_faithfulness_llm(
                entry["question"],
                entry["answer"],
                entry["context_chunks"],
            )

            score = result.get("score", -1)

            if score >= 0:
                _stats["total_scored"] += 1
                _stats["scores"].append(score)
                # Keep rolling window at 200
                if len(_stats["scores"]) > 200:
                    _stats["scores"] = _stats["scores"][-200:]

                _stats["min_score"] = min(_stats["min_score"], score)
                _stats["max_score"] = max(_stats["max_score"], score)

                # Log warning for low faithfulness
                if score < SCORE_THRESHOLD_WARN:
                    logger.warning(
                        f"⚠️ Low faithfulness ({score:.2f}): "
                        f"Q: {entry['question'][:80]}... | "
                        f"Reason: {result.get('reason', 'unknown')}"
                    )
                else:
                    logger.debug(f"📊 Faithfulness: {score:.2f} for: {entry['question'][:60]}...")

                # Save to DB (fire-and-forget)
                await _save_score_to_db(entry, result)

        except Exception as e:
            logger.error(f"Faithfulness worker error: {e}")

        # Small delay between evaluations to avoid API rate limits
        await asyncio.sleep(2)


def start_worker():
    """Start the background faithfulness worker. Call during app startup."""
    global _worker_task

    if not ENABLED:
        logger.info("📊 Faithfulness monitor: DISABLED")
        return

    try:
        loop = asyncio.get_event_loop()
        _worker_task = loop.create_task(_worker_loop())
        logger.info(f"📊 Faithfulness monitor: ON (sample_rate={SAMPLE_RATE:.0%}, judge={JUDGE_MODEL})")
    except Exception as e:
        logger.warning(f"Could not start faithfulness worker: {e}")


def stop_worker():
    """Stop the background worker gracefully."""
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        _worker_task = None
        logger.info("📊 Faithfulness monitor: stopped")
