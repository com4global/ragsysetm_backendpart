"""
RAG Evaluation Runner — Phase 5: Evaluation Framework
=====================================================
Offline evaluation script that measures RAG pipeline quality.

Uses LLM-as-judge pattern (lightweight, no heavy dependencies):
1. Faithfulness: Are claims supported by retrieved chunks?
2. Answer Relevancy: Does the answer address the question?
3. Citation Accuracy: Are citations correct and present?
4. Content Match: Does the answer contain expected keywords?

Usage:
    # Run from command line:
    python evaluations/eval_runner.py
    
    # Or programmatically:
    from evaluations.eval_runner import run_evaluation
    results = run_evaluation(user_id="your-user-id")
"""

import os
import sys
import json
import time
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# LOAD GOLDEN DATASET
# ──────────────────────────────────────────────────────────────

def load_golden_dataset(path: str = None) -> List[Dict]:
    """Load the golden QA evaluation dataset."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "golden_qa.json")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data.get("eval_pairs", [])


# ──────────────────────────────────────────────────────────────
# EVALUATION METRICS (LLM-as-Judge)
# ──────────────────────────────────────────────────────────────

def _judge_with_llm(prompt: str) -> Dict:
    """Use GPT-4o-mini as a judge to score an answer."""
    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        load_dotenv()
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an evaluation judge. Score the answer precisely. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"LLM judge failed: {e}")
        return {"error": str(e)}


def evaluate_faithfulness(question: str, answer: str, context_chunks: List[str]) -> Dict:
    """
    Faithfulness: Are claims in the answer supported by the retrieved chunks?
    Score: 0.0-1.0
    """
    if not context_chunks:
        return {"score": 0.0, "reason": "No context chunks to verify against"}
    
    context_text = "\n---\n".join(context_chunks[:5])  # Limit to top 5 chunks
    
    prompt = f"""Evaluate FAITHFULNESS of this answer. Check if every factual claim in the answer is supported by the provided context chunks.

QUESTION: {question}

CONTEXT CHUNKS:
{context_text}

ANSWER: {answer}

Score from 0.0 to 1.0:
- 1.0 = Every claim is directly supported by the context
- 0.7 = Most claims supported, minor unsupported details
- 0.5 = Mix of supported and unsupported claims
- 0.3 = Mostly unsupported by context
- 0.0 = Answer contradicts or ignores context entirely

Return JSON: {{"score": float, "supported_claims": int, "unsupported_claims": int, "reason": "brief explanation"}}"""
    
    return _judge_with_llm(prompt)


def evaluate_relevancy(question: str, answer: str) -> Dict:
    """
    Answer Relevancy: Does the answer actually address the question?
    Score: 0.0-1.0
    """
    prompt = f"""Evaluate RELEVANCY of this answer to the question. Does it directly address what was asked?

QUESTION: {question}

ANSWER: {answer}

Score from 0.0 to 1.0:
- 1.0 = Directly and completely answers the question
- 0.7 = Mostly answers but misses some aspects
- 0.5 = Partially relevant
- 0.3 = Tangentially related
- 0.0 = Completely off-topic

Return JSON: {{"score": float, "reason": "brief explanation"}}"""
    
    return _judge_with_llm(prompt)


def evaluate_citation_accuracy(answer: str, expected_doc: str, should_cite: bool) -> Dict:
    """
    Citation Accuracy: Does the answer properly cite sources?
    """
    import re
    
    # Find citations in answer
    citation_pattern = r'\[([^\]]+\.(?:pdf|docx|doc|txt|csv|xlsx))\s*(?:,\s*Page\s*\w+)?\]'
    citations = re.findall(citation_pattern, answer, re.IGNORECASE)
    
    # Check general knowledge markers
    general_markers = ["not from your documents", "general knowledge", "📌"]
    is_labeled_general = any(m.lower() in answer.lower() for m in general_markers)
    
    score = 0.0
    reason = ""
    
    if should_cite:
        # Should cite document
        if citations:
            if expected_doc and any(expected_doc.lower() in c.lower() for c in citations):
                score = 1.0
                reason = f"Correctly cites {expected_doc}"
            elif citations:
                score = 0.7
                reason = f"Has citations but not the expected doc. Found: {citations}"
            else:
                score = 0.3
                reason = "No citations found when document-based answer expected"
        else:
            score = 0.0
            reason = "No citations at all — should have cited documents"
    else:
        # Should NOT cite document (general knowledge question)
        if is_labeled_general and not citations:
            score = 1.0
            reason = "Correctly labeled as general knowledge, no false citations"
        elif is_labeled_general:
            score = 0.8
            reason = "Labeled as general knowledge (good) but also has citations (unnecessary)"
        elif citations:
            score = 0.3
            reason = "Falsely cited documents for a general knowledge question"
        else:
            score = 0.5
            reason = "No citation and no general knowledge label"
    
    return {
        "score": score,
        "citations_found": citations,
        "is_labeled_general": is_labeled_general,
        "reason": reason
    }


def evaluate_content_match(answer: str, expected_keywords: List[str]) -> Dict:
    """
    Content Match: Does the answer contain expected keywords/phrases?
    """
    if not expected_keywords:
        return {"score": 1.0, "matched": [], "missed": [], "reason": "No keywords to check"}
    
    matched = []
    missed = []
    
    answer_lower = answer.lower()
    for keyword in expected_keywords:
        if keyword.lower() in answer_lower:
            matched.append(keyword)
        else:
            missed.append(keyword)
    
    score = len(matched) / len(expected_keywords)
    
    return {
        "score": round(score, 2),
        "matched": matched,
        "missed": missed,
        "reason": f"{len(matched)}/{len(expected_keywords)} keywords found"
    }


# ──────────────────────────────────────────────────────────────
# MAIN EVALUATION RUNNER
# ──────────────────────────────────────────────────────────────

def run_evaluation(
    user_id: str = None,
    dataset_path: str = None,
    save_results: bool = True
) -> Dict:
    """
    Run full evaluation suite against the golden dataset.
    
    Args:
        user_id: User ID to run queries as (needed for user-isolated search)
        dataset_path: Path to golden QA JSON file
        save_results: Whether to save results to file
        
    Returns:
        Complete evaluation report with per-question and aggregate scores
    """
    # Load dataset
    eval_pairs = load_golden_dataset(dataset_path)
    
    if not eval_pairs:
        return {"error": "No evaluation pairs found in dataset"}
    
    logger.info(f"📋 Starting evaluation with {len(eval_pairs)} QA pairs...")
    
    results = []
    total_start = time.time()
    
    for i, pair in enumerate(eval_pairs):
        q_id = pair.get("id", f"q_{i}")
        question = pair["question"]
        expected_keywords = pair.get("expected_answer_contains", [])
        expected_doc = pair.get("expected_doc")
        should_cite = pair.get("should_cite_document", True)
        
        logger.info(f"  [{i+1}/{len(eval_pairs)}] Evaluating: {question[:60]}...")
        
        try:
            # Run the actual RAG pipeline
            from QueryProcessor import process_user_query
            
            start = time.time()
            result = process_user_query(question, user_id=user_id)
            latency_ms = (time.time() - start) * 1000
            
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            
            # Extract chunk texts from sources for faithfulness check
            context_chunks = []
            for s in sources:
                if s.get("doc_name"):
                    context_chunks.append(f"[{s['doc_name']}] (source)")
            
            # Run evaluations
            content_score = evaluate_content_match(answer, expected_keywords)
            citation_score = evaluate_citation_accuracy(answer, expected_doc, should_cite)
            relevancy_score = evaluate_relevancy(question, answer)
            
            # Faithfulness only for document-grounded questions
            faithfulness_score = {"score": None, "reason": "Skipped for general knowledge"}
            if should_cite and sources:
                faithfulness_score = evaluate_faithfulness(question, answer, context_chunks)
            
            eval_result = {
                "id": q_id,
                "question": question,
                "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer,
                "latency_ms": round(latency_ms, 1),
                "sources_count": len(sources),
                "citation_coverage": result.get("citation_coverage", 0),
                "scores": {
                    "content_match": content_score.get("score", 0),
                    "citation_accuracy": citation_score.get("score", 0),
                    "relevancy": relevancy_score.get("score", 0),
                    "faithfulness": faithfulness_score.get("score"),
                },
                "details": {
                    "content_match": content_score,
                    "citation_accuracy": citation_score,
                    "relevancy": relevancy_score,
                    "faithfulness": faithfulness_score,
                },
                "status": "pass" if (
                    content_score.get("score", 0) >= 0.5 and
                    citation_score.get("score", 0) >= 0.5
                ) else "fail"
            }
            
            results.append(eval_result)
            
            status_icon = "✅" if eval_result["status"] == "pass" else "❌"
            logger.info(
                f"    {status_icon} content={content_score.get('score', 0):.1f} "
                f"citation={citation_score.get('score', 0):.1f} "
                f"relevancy={relevancy_score.get('score', 0):.1f} "
                f"({latency_ms:.0f}ms)"
            )
            
        except Exception as e:
            logger.error(f"    ❌ Evaluation failed for {q_id}: {e}")
            results.append({
                "id": q_id,
                "question": question,
                "status": "error",
                "error": str(e)
            })
    
    total_time = time.time() - total_start
    
    # Aggregate scores
    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = sum(1 for r in results if r.get("status") == "fail")
    errors = sum(1 for r in results if r.get("status") == "error")
    
    def avg_score(key):
        valid = [r["scores"][key] for r in results if r.get("scores", {}).get(key) is not None]
        return round(sum(valid) / len(valid), 2) if valid else None
    
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_pairs": len(eval_pairs),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "pass_rate": round(passed / max(len(eval_pairs), 1), 2),
        "total_time_seconds": round(total_time, 1),
        "aggregate_scores": {
            "content_match": avg_score("content_match"),
            "citation_accuracy": avg_score("citation_accuracy"),
            "relevancy": avg_score("relevancy"),
            "faithfulness": avg_score("faithfulness"),
        },
        "results": results
    }
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 EVALUATION REPORT")
    logger.info(f"{'='*60}")
    logger.info(f"  Pass Rate: {passed}/{len(eval_pairs)} ({report['pass_rate']*100:.0f}%)")
    logger.info(f"  Content Match:     {report['aggregate_scores']['content_match']}")
    logger.info(f"  Citation Accuracy: {report['aggregate_scores']['citation_accuracy']}")
    logger.info(f"  Relevancy:         {report['aggregate_scores']['relevancy']}")
    logger.info(f"  Faithfulness:      {report['aggregate_scores']['faithfulness']}")
    logger.info(f"  Total Time:        {total_time:.1f}s")
    logger.info(f"{'='*60}")
    
    # Save results
    if save_results:
        results_path = os.path.join(
            os.path.dirname(__file__), 
            f"eval_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        try:
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"📁 Results saved to: {results_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save results: {e}")
    
    return report


# ──────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    # Get user_id from command line or use default
    user_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not user_id:
        print("Usage: python eval_runner.py <user_id>")
        print("  user_id: The Supabase user UUID to run evaluation as")
        print("\nRunning without user_id (limited to general questions)...")
    
    report = run_evaluation(user_id=user_id)
    
    print(f"\n✅ Evaluation complete! Pass rate: {report['pass_rate']*100:.0f}%")
