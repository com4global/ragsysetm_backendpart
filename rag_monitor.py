"""
RAG Monitor — Phase 4: Monitoring & Observability
==================================================
Lightweight monitoring layer for the RAG pipeline.
Tracks every query with detailed metrics, stored in Supabase usage_logs.

Features:
1. Per-query tracing: latency breakdown per pipeline stage
2. Cost estimation: embedding + LLM token costs
3. Quality metrics: citation coverage, retrieval stats
4. Performance percentiles: P50/P95 latency tracking
5. Dashboard data: admin API for viewing metrics

Zero impact on existing code — purely additive, all wrapped in try/except.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# COST CONSTANTS (USD per token/request, updated Feb 2026)
# ──────────────────────────────────────────────────────────────

COST_TABLE = {
    "openai": {
        "embedding": {
            "text-embedding-3-small": {"per_token": 0.00000002},  # $0.02 per 1M tokens
        },
        "chat": {
            "gpt-4o-mini": {
                "input_per_token": 0.00000015,   # $0.15 per 1M tokens
                "output_per_token": 0.0000006,   # $0.60 per 1M tokens
            },
        },
    },
}


# ──────────────────────────────────────────────────────────────
# QUERY TRACE — captures one full RAG pipeline execution
# ──────────────────────────────────────────────────────────────

class QueryTrace:
    """
    Trace a single RAG query through the full pipeline.
    
    Usage:
        trace = QueryTrace(user_id, query)
        trace.record_stage("embed", latency_ms=45)
        trace.record_stage("vector_search", latency_ms=120, extra={"results": 10})
        trace.record_stage("bm25_search", latency_ms=80, extra={"results": 5})
        trace.record_stage("rerank", latency_ms=200, extra={"results": 5})
        trace.record_stage("llm", latency_ms=1500, extra={"tokens_in": 800, "tokens_out": 200})
        trace.finalize(answer, sources, citation_coverage)
        trace.save()  # Persist to Supabase
    """
    
    def __init__(self, user_id: str, query: str):
        self.user_id = user_id
        self.query = query[:500]  # Truncate for storage
        self.start_time = time.time()
        self.stages: List[Dict] = []
        self.finalized = False
        self.result_data: Dict = {}
    
    def record_stage(self, name: str, latency_ms: float = 0, extra: Dict = None):
        """Record a pipeline stage's metrics."""
        self.stages.append({
            "name": name,
            "latency_ms": round(latency_ms, 1),
            "timestamp": time.time(),
            **(extra or {})
        })
    
    def finalize(
        self, 
        answer: str = "",
        sources: List = None,
        citation_coverage: float = 0.0,
        is_grounded: bool = False,
        chunks_retrieved: int = 0,
        bm25_used: bool = False,
        reranker_used: bool = False,
        error: str = None
    ):
        """Finalize the trace with result data."""
        total_ms = (time.time() - self.start_time) * 1000
        
        # Estimate token counts from context
        # Rough: 1 token ≈ 4 chars for English
        answer_tokens = len(answer) // 4 if answer else 0
        
        # Sum up tokens from stages
        input_tokens = 0
        output_tokens = 0
        for stage in self.stages:
            input_tokens += stage.get("tokens_in", 0)
            output_tokens += stage.get("tokens_out", 0)
        
        # If no explicit token counts, estimate
        if input_tokens == 0:
            input_tokens = len(self.query) // 4 + (chunks_retrieved * 150)  # ~150 tokens per chunk
        if output_tokens == 0:
            output_tokens = answer_tokens
        
        # Estimate cost
        embed_cost = (len(self.query) // 4) * COST_TABLE["openai"]["embedding"]["text-embedding-3-small"]["per_token"]
        llm_input_cost = input_tokens * COST_TABLE["openai"]["chat"]["gpt-4o-mini"]["input_per_token"]
        llm_output_cost = output_tokens * COST_TABLE["openai"]["chat"]["gpt-4o-mini"]["output_per_token"]
        total_cost = embed_cost + llm_input_cost + llm_output_cost
        
        self.result_data = {
            "total_latency_ms": round(total_ms, 1),
            "stages": {s["name"]: s["latency_ms"] for s in self.stages},
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "citation_coverage": citation_coverage,
            "is_grounded": is_grounded,
            "chunks_retrieved": chunks_retrieved,
            "sources_count": len(sources) if sources else 0,
            "bm25_used": bm25_used,
            "reranker_used": reranker_used,
            "error": error,
            "has_answer": bool(answer and len(answer) > 10),
        }
        self.finalized = True
    
    def save(self):
        """Persist trace to Supabase usage_logs table."""
        if not self.finalized:
            return
        
        try:
            from database import supabase
            if not supabase:
                return
            
            supabase.table("usage_logs").insert({
                "user_id": self.user_id,
                "service": "openai",
                "action": "rag_query",
                "tokens_used": self.result_data.get("total_tokens", 0),
                "cost_usd": self.result_data.get("estimated_cost_usd", 0),
                "metadata": {
                    "query": self.query,
                    **self.result_data
                }
            }).execute()
            
            logger.debug(f"📊 Query trace saved: {self.result_data['total_latency_ms']}ms, ${self.result_data['estimated_cost_usd']:.6f}")
            
        except Exception as e:
            logger.warning(f"⚠️ Query trace save failed (non-critical): {e}")


# ──────────────────────────────────────────────────────────────
# AGGREGATED METRICS — for admin dashboard
# ──────────────────────────────────────────────────────────────

def get_rag_metrics(days: int = 7, user_id: str = None) -> Dict:
    """
    Get aggregated RAG performance metrics for the admin dashboard.
    
    Args:
        days: Number of days to look back
        user_id: Optional filter for a specific user
        
    Returns:
        Dict with P50/P95 latency, avg cost, citation stats, etc.
    """
    try:
        from database import supabase
        if not supabase:
            return {"error": "Supabase not available"}
        
        # Fetch RAG query logs
        query = supabase.table("usage_logs") \
            .select("tokens_used, cost_usd, metadata, created_at") \
            .eq("action", "rag_query") \
            .gte("created_at", (datetime.utcnow() - timedelta(days=days)).isoformat())
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        result = query.order("created_at", desc=True).limit(1000).execute()
        logs = result.data or []
        
        if not logs:
            return {
                "total_queries": 0,
                "period_days": days,
                "message": "No RAG queries recorded yet"
            }
        
        # Extract metrics
        latencies = []
        costs = []
        coverages = []
        grounded_count = 0
        error_count = 0
        bm25_count = 0
        rerank_count = 0
        stage_latencies = defaultdict(list)
        
        for log in logs:
            meta = log.get("metadata", {})
            
            latency = meta.get("total_latency_ms", 0)
            if latency > 0:
                latencies.append(latency)
            
            cost = log.get("cost_usd", 0)
            if cost:
                costs.append(float(cost))
            
            coverage = meta.get("citation_coverage", 0)
            if coverage is not None:
                coverages.append(coverage)
            
            if meta.get("is_grounded"):
                grounded_count += 1
            if meta.get("error"):
                error_count += 1
            if meta.get("bm25_used"):
                bm25_count += 1
            if meta.get("reranker_used"):
                rerank_count += 1
            
            # Stage-level latencies
            for stage_name, stage_ms in meta.get("stages", {}).items():
                stage_latencies[stage_name].append(stage_ms)
        
        total = len(logs)
        
        # Calculate percentiles
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return round(sorted_data[min(idx, len(sorted_data) - 1)], 1)
        
        # Stage breakdown (P50)
        stage_p50 = {}
        for stage, values in stage_latencies.items():
            stage_p50[stage] = percentile(values, 50)
        
        return {
            "total_queries": total,
            "period_days": days,
            "latency": {
                "p50_ms": percentile(latencies, 50),
                "p95_ms": percentile(latencies, 95),
                "avg_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "stage_breakdown_p50": stage_p50,
            },
            "cost": {
                "total_usd": round(sum(costs), 4),
                "avg_per_query_usd": round(sum(costs) / len(costs), 6) if costs else 0,
                "total_tokens": sum(log.get("tokens_used", 0) for log in logs),
            },
            "quality": {
                "avg_citation_coverage": round(sum(coverages) / len(coverages), 2) if coverages else 0,
                "grounded_rate": round(grounded_count / total, 2) if total else 0,
                "error_rate": round(error_count / total, 2) if total else 0,
            },
            "features": {
                "bm25_usage_rate": round(bm25_count / total, 2) if total else 0,
                "reranker_usage_rate": round(rerank_count / total, 2) if total else 0,
            }
        }
    
    except Exception as e:
        logger.error(f"❌ Failed to compute RAG metrics: {e}")
        return {"error": str(e)}
