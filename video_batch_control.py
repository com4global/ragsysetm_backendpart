"""
video_batch_control.py — Per-User Video Generation Control
===========================================================
Provides admin + user facing controls for video batch generation.
Tracks Replicate API credit usage per user.

SAFETY: This module is 100% additive. It does NOT modify any existing
functions or endpoints. All existing behavior is preserved.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Replicate Credit Tracking ──────────────────────────────────────────────────

def track_replicate_usage(
    user_id: str,
    action: str,
    model: str = "",
    credits: float = 0.0,
    topic: str = "",
    doc_name: str = "",
    duration_ms: float = 0.0,
    status: str = "completed",
    metadata: Optional[Dict] = None,
):
    """
    Log a Replicate API usage event for a user.
    Call this after every Replicate API call (video gen, TTS, etc.)
    
    Fire-and-forget — never raises, never blocks.
    """
    try:
        from database import supabase
        supabase.table("replicate_usage").insert({
            "user_id": user_id,
            "action": action,
            "model": model,
            "credits": credits,
            "topic": topic[:200] if topic else "",
            "doc_name": doc_name[:200] if doc_name else "",
            "duration_ms": duration_ms,
            "status": status,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.debug(f"Replicate usage tracking failed (non-critical): {e}")


def get_user_replicate_usage(user_id: str) -> Dict[str, Any]:
    """Get aggregated Replicate usage for a single user."""
    try:
        from database import supabase
        result = supabase.table("replicate_usage") \
            .select("action,credits,status,created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()
        
        records = result.data or []
        total_credits = sum(r.get("credits", 0) for r in records)
        completed = sum(1 for r in records if r.get("status") == "completed")
        failed = sum(1 for r in records if r.get("status") == "failed")
        
        return {
            "user_id": user_id,
            "total_credits": round(total_credits, 4),
            "total_calls": len(records),
            "completed": completed,
            "failed": failed,
            "recent": records[:20],
        }
    except Exception as e:
        logger.debug(f"Replicate usage fetch failed: {e}")
        return {"user_id": user_id, "total_credits": 0, "total_calls": 0, "recent": []}


def get_all_users_replicate_usage() -> list:
    """Get aggregated Replicate usage for ALL users (admin view)."""
    try:
        from database import supabase
        
        # Get all usage grouped by user
        result = supabase.table("replicate_usage") \
            .select("user_id,action,credits,status,created_at") \
            .order("created_at", desc=True) \
            .limit(500) \
            .execute()
        
        records = result.data or []
        
        # Aggregate per user
        user_map = {}
        for r in records:
            uid = r.get("user_id", "unknown")
            if uid not in user_map:
                user_map[uid] = {"user_id": uid, "total_credits": 0, "total_calls": 0, "completed": 0, "failed": 0}
            user_map[uid]["total_credits"] += r.get("credits", 0)
            user_map[uid]["total_calls"] += 1
            if r.get("status") == "completed":
                user_map[uid]["completed"] += 1
            elif r.get("status") == "failed":
                user_map[uid]["failed"] += 1
        
        # Round credits
        for uid in user_map:
            user_map[uid]["total_credits"] = round(user_map[uid]["total_credits"], 4)
        
        return list(user_map.values())
    except Exception as e:
        logger.debug(f"All users replicate usage fetch failed: {e}")
        return []


# ── Per-User Video Generation Control ────────────────────────────────────────

def is_video_generation_enabled(user_id: str) -> bool:
    """Check if video generation is enabled for a user."""
    try:
        from database import supabase
        result = supabase.table("profiles") \
            .select("video_generation_enabled") \
            .eq("id", user_id) \
            .single() \
            .execute()
        
        if result.data:
            return result.data.get("video_generation_enabled", False)
        return False
    except Exception as e:
        logger.debug(f"Video gen enabled check failed: {e}")
        return False


def set_video_generation_enabled(user_id: str, enabled: bool) -> bool:
    """Enable or disable video generation for a user. Returns success."""
    try:
        from database import supabase
        supabase.table("profiles") \
            .update({"video_generation_enabled": enabled}) \
            .eq("id", user_id) \
            .execute()
        logger.info(f"{'✅' if enabled else '⏸️'} Video generation {'enabled' if enabled else 'disabled'} for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to set video gen enabled: {e}")
        return False


def get_all_users_batch_status() -> list:
    """
    Get ALL users' batch job status with their video generation flag.
    Used by admin to see the full picture.
    """
    try:
        from database import supabase
        
        # 1. Get all profiles with video_generation_enabled flag
        profiles_result = supabase.table("profiles") \
            .select("id,full_name,email,role,video_generation_enabled") \
            .execute()
        profiles = {p["id"]: p for p in (profiles_result.data or [])}
        
        # 2. Get all batch_jobs (recent, up to 200)
        jobs_result = supabase.table("batch_jobs") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(200) \
            .execute()
        jobs = jobs_result.data or []
        
        # 3. Get replicate usage aggregates
        usage_result = supabase.table("replicate_usage") \
            .select("user_id,credits") \
            .execute()
        usage_map = {}
        for u in (usage_result.data or []):
            uid = u.get("user_id", "")
            usage_map[uid] = usage_map.get(uid, 0) + u.get("credits", 0)
        
        # 4. Aggregate per user
        user_data = {}
        for job in jobs:
            uid = job.get("user_id", "unknown")
            if uid not in user_data:
                profile = profiles.get(uid, {})
                user_data[uid] = {
                    "user_id": uid,
                    "email": profile.get("email", "unknown"),
                    "full_name": profile.get("full_name", ""),
                    "role": profile.get("role", ""),
                    "video_generation_enabled": profile.get("video_generation_enabled", False),
                    "replicate_credits": round(usage_map.get(uid, 0), 4),
                    "jobs": [],
                    "total_jobs": 0,
                    "completed_jobs": 0,
                    "active_jobs": 0,
                    "failed_jobs": 0,
                }
            entry = user_data[uid]
            entry["total_jobs"] += 1
            status = job.get("status", "")
            if status == "completed":
                entry["completed_jobs"] += 1
            elif status == "failed":
                entry["failed_jobs"] += 1
            elif status in ("queued", "processing", "extracting_topics", "generating_lessons", "generating_videos"):
                entry["active_jobs"] += 1
            entry["jobs"].append(job)
        
        # Add profiles that have no jobs yet
        for uid, profile in profiles.items():
            if uid not in user_data:
                user_data[uid] = {
                    "user_id": uid,
                    "email": profile.get("email", "unknown"),
                    "full_name": profile.get("full_name", ""),
                    "role": profile.get("role", ""),
                    "video_generation_enabled": profile.get("video_generation_enabled", False),
                    "replicate_credits": round(usage_map.get(uid, 0), 4),
                    "jobs": [],
                    "total_jobs": 0,
                    "completed_jobs": 0,
                    "active_jobs": 0,
                    "failed_jobs": 0,
                }
        
        return list(user_data.values())
    except Exception as e:
        logger.error(f"Admin batch status fetch failed: {e}")
        return []
