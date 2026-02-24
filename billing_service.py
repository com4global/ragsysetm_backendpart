"""
billing_service.py — Stripe Subscription Management
=====================================================
Handles plan management, Stripe Checkout sessions,
webhook processing, and customer portal for the app.

Plans:
  free      → $0/mo  — PDF only, 3 MB/file, 20 MB total, 200 chunks
  pro       → $25/mo — All types, 25 MB/file, 200 MB total, 2,000 chunks
  plus      → $60/mo — All types, 100 MB/file, 1 GB total, 10,000 chunks
  corporate → $100/mo — All types, 500 MB/file, unlimited total, unlimited chunks
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Plan definitions ─────────────────────────────────────────────────────────

PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_usd": 0,
        "price_inr": 0,
        "upload_limit_mb": 10,
        "max_file_size_mb": 3,
        "max_total_storage_mb": 20,
        "allowed_file_types": [".pdf"],
        "chunk_limit": 200,
        "description": "Get started — no credit card required",
        "features": [
            "PDF uploads up to 3 MB each",
            "20 MB total storage",
            "200 RAG chunks",
            "Basic AI chat",
            "1 document at a time",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_usd": 25,
        "price_inr": 2100,
        "upload_limit_mb": 100,
        "max_file_size_mb": 25,
        "max_total_storage_mb": 200,
        "allowed_file_types": "all",
        "chunk_limit": 2000,
        "description": "For professionals who need more power",
        "features": [
            "All file formats, up to 25 MB each",
            "200 MB total storage",
            "2,000 RAG chunks",
            "AI Teacher videos",
            "Legal Analysis",
            "Priority support",
        ],
        "price_id_usd": os.getenv("STRIPE_PRICE_PRO_USD", ""),
        "price_id_inr": os.getenv("STRIPE_PRICE_PRO_INR", ""),
    },
    "plus": {
        "name": "Plus",
        "price_usd": 60,
        "price_inr": 5000,
        "upload_limit_mb": 500,
        "max_file_size_mb": 100,
        "max_total_storage_mb": 1024,
        "allowed_file_types": "all",
        "chunk_limit": 10000,
        "description": "For power users and small teams",
        "features": [
            "All file formats, up to 100 MB each",
            "1 GB total storage",
            "10,000 RAG chunks",
            "All Pro features",
            "Multiple document sessions",
            "Advanced analytics",
        ],
        "price_id_usd": os.getenv("STRIPE_PRICE_PLUS_USD", ""),
        "price_id_inr": os.getenv("STRIPE_PRICE_PLUS_INR", ""),
    },
    "corporate": {
        "name": "Corporate",
        "price_usd": 100,
        "price_inr": 8300,
        "upload_limit_mb": -1,   # -1 = unlimited
        "max_file_size_mb": 500,  # 500 MB per file
        "max_total_storage_mb": -1,  # -1 = unlimited
        "allowed_file_types": "all",
        "chunk_limit": -1,       # -1 = unlimited
        "description": "Unlimited access for enterprises",
        "features": [
            "All file formats, up to 500 MB each",
            "Unlimited total storage",
            "Unlimited RAG chunks",
            "All Plus features",
            "Custom integrations",
            "Dedicated support",
            "Team management",
        ],
        "price_id_usd": os.getenv("STRIPE_PRICE_CORPORATE_USD", ""),
        "price_id_inr": os.getenv("STRIPE_PRICE_CORPORATE_INR", ""),
    },
}


def get_plan(plan_name: str) -> Dict[str, Any]:
    """Return plan config dict. Falls back to 'free' if unknown."""
    return PLANS.get(plan_name, PLANS["free"])


def check_upload_allowed(plan_name: str, file_size_bytes: int) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    file_size_bytes: size of file being uploaded.
    """
    plan = get_plan(plan_name)
    limit_mb = plan["upload_limit_mb"]
    if limit_mb == -1:
        return True, ""
    file_mb = file_size_bytes / (1024 * 1024)
    if file_mb > limit_mb:
        return False, (
            f"File size {file_mb:.1f} MB exceeds your {plan['name']} plan limit of {limit_mb} MB. "
            f"Upgrade to upload larger documents."
        )
    return True, ""


def check_chunks_allowed(plan_name: str, current_chunks: int) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    current_chunks: how many chunks the user already has stored.
    """
    plan = get_plan(plan_name)
    limit = plan["chunk_limit"]
    if limit == -1:
        return True, ""
    if current_chunks >= limit:
        return False, (
            f"You've reached your {plan['name']} plan chunk limit of {limit:,}. "
            f"Upgrade to store more documents."
        )
    return True, ""


def check_file_type_allowed(plan_name: str, filename: str) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Checks whether the file extension is permitted for the user's plan.
    """
    plan = get_plan(plan_name)
    allowed = plan.get("allowed_file_types", "all")
    if allowed == "all":
        return True, ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        allowed_str = ", ".join(t.upper().replace(".", "") for t in allowed)
        return False, (
            f"Your {plan['name']} plan only supports {allowed_str} files. "
            f"Upgrade to upload {ext.upper().replace('.', '')} and other formats."
        )
    return True, ""


def check_total_storage(plan_name: str, current_used_bytes: int, new_file_bytes: int) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Checks whether the user has enough total storage remaining.
    """
    plan = get_plan(plan_name)
    limit_mb = plan.get("max_total_storage_mb", -1)
    if limit_mb == -1:
        return True, ""
    limit_bytes = limit_mb * 1024 * 1024
    new_total = current_used_bytes + new_file_bytes
    if new_total > limit_bytes:
        used_mb = current_used_bytes / (1024 * 1024)
        return False, (
            f"Adding this file would exceed your {plan['name']} plan storage limit of {limit_mb} MB "
            f"(currently using {used_mb:.1f} MB). Upgrade for more storage."
        )
    return True, ""


def check_file_size(plan_name: str, file_size_bytes: int) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Checks per-file size limit (max_file_size_mb).
    """
    plan = get_plan(plan_name)
    limit_mb = plan.get("max_file_size_mb", -1)
    if limit_mb == -1:
        return True, ""
    file_mb = file_size_bytes / (1024 * 1024)
    if file_mb > limit_mb:
        return False, (
            f"File size {file_mb:.1f} MB exceeds your {plan['name']} plan limit of {limit_mb} MB per file. "
            f"Upgrade to upload larger files."
        )
    return True, ""


# ── Stripe helpers ────────────────────────────────────────────────────────────

def _get_stripe():
    """Lazy-import stripe so the app works without STRIPE_SECRET_KEY in dev."""
    import stripe as _stripe
    _stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    if not _stripe.api_key:
        logger.warning("STRIPE_SECRET_KEY not set — Stripe calls will fail")
    return _stripe


def get_or_create_customer(user_id: str, email: str) -> str:
    """Find or create a Stripe customer for this user. Returns customer_id."""
    stripe = _get_stripe()
    from database import supabase as sb

    # Check DB first
    try:
        result = sb.table("subscriptions") \
            .select("stripe_customer_id") \
            .eq("user_id", user_id) \
            .limit(1).execute()
        if result.data and result.data[0].get("stripe_customer_id"):
            return result.data[0]["stripe_customer_id"]
    except Exception as e:
        logger.warning(f"Supabase customer lookup failed: {e}")

    # Create Stripe customer
    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": user_id},
    )
    customer_id = customer["id"]

    # Upsert into DB
    try:
        sb.table("subscriptions").upsert(
            {"user_id": user_id, "stripe_customer_id": customer_id, "plan": "free", "status": "active"},
            on_conflict="user_id"
        ).execute()
    except Exception as e:
        logger.warning(f"Supabase customer save failed: {e}")

    return customer_id


def create_checkout_session(
    user_id: str,
    email: str,
    plan: str,
    currency: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout session and return the URL."""
    stripe = _get_stripe()
    plan_info = PLANS.get(plan)
    if not plan_info:
        raise ValueError(f"Unknown plan: {plan}")

    price_key = f"price_id_{currency.lower()}"
    price_id = plan_info.get(price_key, "")
    if not price_id:
        raise ValueError(
            f"No Stripe price ID configured for plan={plan}, currency={currency}. "
            "Set STRIPE_PRICE_* env vars and create products in Stripe Dashboard."
        )

    customer_id = get_or_create_customer(user_id, email)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,   # already includes ?session_id={CHECKOUT_SESSION_ID} from the frontend
        cancel_url=cancel_url,
        metadata={"user_id": user_id, "plan": plan},
        currency=currency.lower(),
        subscription_data={"metadata": {"user_id": user_id, "plan": plan}},
    )
    return session.url


def create_portal_session(user_id: str, return_url: str) -> str:
    """Return a Stripe Customer Portal URL for managing the subscription."""
    stripe = _get_stripe()
    from database import supabase as sb

    result = sb.table("subscriptions") \
        .select("stripe_customer_id") \
        .eq("user_id", user_id) \
        .limit(1).execute()

    if not result.data or not result.data[0].get("stripe_customer_id"):
        raise ValueError("No Stripe customer found for this user.")

    customer_id = result.data[0]["stripe_customer_id"]
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def handle_webhook_event(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Verify and process a Stripe webhook event.
    Updates Supabase subscriptions table on payment events.
    Returns dict with handled=True/False.
    """
    stripe = _get_stripe()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    from database import supabase as sb

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        logger.error("Stripe webhook signature verification failed")
        raise ValueError("Invalid signature")

    event_type = event["type"]
    logger.info(f"Stripe webhook: {event_type}")

    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        sub = event["data"]["object"]
        customer_id = sub["customer"]
        status = sub["status"]  # active, canceled, past_due, etc.
        user_id = sub.get("metadata", {}).get("user_id")
        plan = sub.get("metadata", {}).get("plan", "free")
        subscription_id = sub["id"]
        period_end = sub.get("current_period_end")

        if status in ("canceled", "unpaid", "past_due"):
            plan = "free"

        try:
            # Update subscriptions table
            sb.table("subscriptions").upsert(
                {
                    "user_id": user_id,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "plan": plan,
                    "status": status,
                    "current_period_end": (
                        __import__("datetime").datetime.utcfromtimestamp(period_end).isoformat()
                        if period_end else None
                    ),
                    "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
                },
                on_conflict="user_id",
            ).execute()
            # Mirror plan into profiles for easy access
            if user_id:
                sb.table("profiles").update({"plan": plan}).eq("id", user_id).execute()
            logger.info(f"✅ Subscription updated: user={user_id} plan={plan} status={status}")
        except Exception as e:
            logger.error(f"Supabase subscription update failed: {e}")

    elif event_type == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("metadata", {}).get("user_id")
        plan = session.get("metadata", {}).get("plan", "free")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        try:
            sb.table("subscriptions").upsert(
                {
                    "user_id": user_id,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "plan": plan,
                    "status": "active",
                    "updated_at": __import__("datetime").datetime.utcnow().isoformat(),
                },
                on_conflict="user_id",
            ).execute()
            if user_id:
                sb.table("profiles").update({"plan": plan}).eq("id", user_id).execute()
            logger.info(f"✅ Checkout completed: user={user_id} plan={plan}")
        except Exception as e:
            logger.error(f"Supabase checkout update failed: {e}")

    return {"handled": True, "event": event_type}


def get_user_subscription(user_id: str) -> Dict[str, Any]:
    """
    Return the user's current subscription info including plan limits.
    Falls back to 'free' if no record exists.
    """
    from database import supabase as sb
    try:
        result = sb.table("subscriptions") \
            .select("plan,status,current_period_end,stripe_customer_id") \
            .eq("user_id", user_id) \
            .limit(1).execute()
        if result.data:
            row = result.data[0]
            plan_name = row.get("plan", "free")
            # Canceled subscriptions revert to free
            if row.get("status") in ("canceled", "unpaid"):
                plan_name = "free"
            plan = get_plan(plan_name)
            return {
                "plan": plan_name,
                "status": row.get("status", "active"),
                "current_period_end": row.get("current_period_end"),
                "has_customer": bool(row.get("stripe_customer_id")),
                "upload_limit_mb": plan["upload_limit_mb"],
                "chunk_limit": plan["chunk_limit"],
            }
    except Exception as e:
        logger.warning(f"Subscription lookup failed: {e}")

    # Default: free
    plan = get_plan("free")
    return {
        "plan": "free",
        "status": "active",
        "current_period_end": None,
        "has_customer": False,
        "upload_limit_mb": plan["upload_limit_mb"],
        "chunk_limit": plan["chunk_limit"],
    }


def _price_id_to_plan() -> Dict[str, str]:
    """Build a reverse map: price_id → plan_key from environment variables."""
    mapping: Dict[str, str] = {}
    for plan_key, plan_info in PLANS.items():
        for currency in ("usd", "inr"):
            pid = plan_info.get(f"price_id_{currency}", "")
            if pid:
                mapping[pid] = plan_key
    return mapping


def verify_checkout_session(session_id: str, user_id: str) -> Dict[str, Any]:
    """
    Directly verify a Stripe Checkout session and update the user's plan.
    Works even when session metadata doesn't contain the plan key (e.g.,
    old payments). Falls back to price-ID reverse lookup.
    """
    from database import supabase as sb
    import datetime

    stripe = _get_stripe()
    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription", "subscription.items"],
        )
    except Exception as e:
        logger.error(f"Stripe session retrieval failed: {e}")
        raise ValueError(f"Could not retrieve session: {e}")

    pay_status = session.get("payment_status")
    logger.info(f"Session {session_id} payment_status={pay_status}")

    if pay_status not in ("paid", "no_payment_required"):
        return {"ok": False, "reason": f"payment_not_completed (status={pay_status})"}

    # ── Resolve plan ──────────────────────────────────────────────────────────
    # Priority: 1) session metadata, 2) price-ID reverse lookup, 3) default "pro"
    plan = session.get("metadata", {}).get("plan", "")
    if not plan or plan == "free":
        # Try to derive plan from the first subscription line item's price ID
        price_id_map = _price_id_to_plan()
        sub = session.get("subscription")
        if isinstance(sub, dict):
            items = sub.get("items", {}).get("data", [])
            for item in items:
                pid = item.get("price", {}).get("id", "")
                if pid in price_id_map:
                    plan = price_id_map[pid]
                    logger.info(f"Resolved plan={plan} from price_id={pid}")
                    break
        if not plan or plan == "free":
            # Last resort: if the user paid something, assume "pro"
            plan = "pro"
            logger.warning(f"Could not resolve plan from metadata or price ID — defaulting to 'pro'")

    customer_id = session.get("customer")
    sub = session.get("subscription")
    subscription_id = sub["id"] if isinstance(sub, dict) else sub
    period_end = None
    if isinstance(sub, dict):
        period_end = sub.get("current_period_end")

    try:
        sb.table("subscriptions").upsert(
            {
                "user_id": user_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "plan": plan,
                "status": "active",
                "current_period_end": (
                    datetime.datetime.utcfromtimestamp(period_end).isoformat()
                    if period_end else None
                ),
                "updated_at": datetime.datetime.utcnow().isoformat(),
            },
            on_conflict="user_id",
        ).execute()
        sb.table("profiles").update({"plan": plan}).eq("id", user_id).execute()
        logger.info(f"✅ verify_checkout_session: user={user_id} plan={plan}")
    except Exception as e:
        logger.error(f"Supabase update failed in verify_checkout_session: {e}")
        raise

    plan_info = get_plan(plan)
    return {
        "ok": True,
        "plan": plan,
        "upload_limit_mb": plan_info["upload_limit_mb"],
        "chunk_limit": plan_info["chunk_limit"],
    }


def sync_active_subscription(user_id: str) -> Dict[str, Any]:
    """
    Sync the user's plan by checking their active Stripe subscriptions directly.
    Used to repair the plan for payments that happened before the verify flow
    was in place, or when the DB record is out of sync.
    """
    from database import supabase as sb
    import datetime

    stripe = _get_stripe()

    # Look up the customer from DB
    try:
        result = sb.table("subscriptions") \
            .select("stripe_customer_id") \
            .eq("user_id", user_id) \
            .limit(1).execute()
        customer_id = result.data[0].get("stripe_customer_id") if result.data else None
    except Exception:
        customer_id = None

    if not customer_id:
        # Try to find the customer by searching Stripe
        try:
            user_result = sb.table("profiles").select("email").eq("id", user_id).single().execute()
            email = user_result.data.get("email") if user_result.data else None
            if email:
                customers = stripe.Customer.list(email=email, limit=1)
                if customers.data:
                    customer_id = customers.data[0]["id"]
        except Exception as e:
            logger.warning(f"Customer lookup fallback failed: {e}")

    if not customer_id:
        return {"ok": False, "reason": "no_stripe_customer_found"}

    # List active subscriptions
    try:
        subs = stripe.Subscription.list(customer=customer_id, status="active", limit=1)
    except Exception as e:
        logger.error(f"Stripe subscription list failed: {e}")
        raise ValueError(f"Stripe error: {e}")

    if not subs.data:
        return {"ok": False, "reason": "no_active_stripe_subscription"}

    sub = subs.data[0]
    subscription_id = sub["id"]
    period_end = sub.get("current_period_end")

    # Resolve plan: metadata first, then price-ID lookup
    plan = sub.get("metadata", {}).get("plan", "")
    price_id_map = _price_id_to_plan()
    if not plan or plan == "free":
        for item in sub.get("items", {}).get("data", []):
            pid = item.get("price", {}).get("id", "")
            if pid in price_id_map:
                plan = price_id_map[pid]
                break
    if not plan or plan == "free":
        plan = "pro"  # paid subscription → at least pro
        logger.warning(f"sync_active_subscription: defaulting to 'pro' for user={user_id}")

    try:
        sb.table("subscriptions").upsert(
            {
                "user_id": user_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "plan": plan,
                "status": "active",
                "current_period_end": (
                    datetime.datetime.utcfromtimestamp(period_end).isoformat()
                    if period_end else None
                ),
                "updated_at": datetime.datetime.utcnow().isoformat(),
            },
            on_conflict="user_id",
        ).execute()
        sb.table("profiles").update({"plan": plan}).eq("id", user_id).execute()
        logger.info(f"✅ sync_active_subscription: user={user_id} plan={plan}")
    except Exception as e:
        logger.error(f"Supabase update failed in sync_active_subscription: {e}")
        raise

    plan_info = get_plan(plan)
    return {
        "ok": True,
        "plan": plan,
        "upload_limit_mb": plan_info["upload_limit_mb"],
        "chunk_limit": plan_info["chunk_limit"],
    }
