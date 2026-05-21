"""
Gateway billing module.
- Checks plan limits before expensive operations.
- Stripe skeleton: safely disabled when STRIPE_SECRET_KEY is missing.
"""
import os
import logging
from typing import Optional

from database import get_db_connection, release_db_connection
from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("gateway.billing")

STRIPE_SECRET_KEY   = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_IDS = {
    "personal": os.getenv("STRIPE_PRICE_PERSONAL", ""),
    "team":     os.getenv("STRIPE_PRICE_TEAM", ""),
    "business": os.getenv("STRIPE_PRICE_BUSINESS", ""),
}


# ─── Plan limit enforcement (works WITHOUT Stripe) ────────────────────────────
def check_workspace_plan_limits(workspace_id: str, action: str):
    """Enforce plan limits before passing request downstream.

    action: 'upload_document' | 'query'
    Raises HTTPException(403) if limit exceeded.
    """
    conn = get_db_connection()
    if not conn:
        logger.warning("DB unavailable — skipping billing check")
        return
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT p.document_limit, p.query_limit_monthly, p.storage_limit_mb
                FROM workspaces w
                LEFT JOIN plans p ON w.plan_id = p.id
                WHERE w.id = %s
                """,
                (workspace_id,),
            )
            plan = cur.fetchone()

        doc_limit   = (plan["document_limit"]      if plan else None) or 3
        query_limit = (plan["query_limit_monthly"] if plan else None) or 50

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if action == "upload_document":
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM documents WHERE workspace_id = %s",
                    (workspace_id,),
                )
                count = cur.fetchone()["cnt"]
                if count >= doc_limit:
                    raise HTTPException(
                        403,
                        f"Document limit reached ({doc_limit}). "
                        "Upgrade your plan to upload more documents.",
                    )

            elif action == "query":
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM queries
                    WHERE workspace_id = %s
                      AND date_trunc('month', created_at) = date_trunc('month', NOW())
                    """,
                    (workspace_id,),
                )
                count = cur.fetchone()["cnt"]
                if count >= query_limit:
                    raise HTTPException(
                        403,
                        f"Monthly query limit reached ({query_limit}). "
                        "Upgrade your plan for more queries.",
                    )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Billing check error: %s", exc)
    finally:
        release_db_connection(conn)


# ─── Stripe Integration Skeleton ─────────────────────────────────────────────
def _stripe_enabled() -> bool:
    return bool(STRIPE_SECRET_KEY)


def get_stripe():
    """Return configured stripe module or raise HTTPException."""
    if not _stripe_enabled():
        raise HTTPException(503, "Billing is not configured on this server")
    import stripe  # type: ignore
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


async def create_stripe_checkout(workspace_id: str, plan_name: str, billing_cycle: str = "monthly"):
    """Create a Stripe Checkout Session for plan upgrade."""
    if not _stripe_enabled():
        logger.info("Stripe not configured — checkout unavailable")
        return None

    stripe = get_stripe()
    price_id = STRIPE_PRICE_IDS.get(plan_name)
    if not price_id:
        raise HTTPException(400, f"Unknown plan: {plan_name}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:8080')}/billing/success",
        cancel_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:8080')}/billing",
        metadata={"workspace_id": workspace_id, "plan": plan_name},
    )
    return session.url


async def update_workspace_plan(workspace_id: str, plan_name: str, stripe_sub_id: Optional[str] = None):
    """Assign a plan to a workspace after successful payment."""
    conn = get_db_connection()
    if not conn:
        logger.error("DB unavailable — cannot update workspace plan")
        return
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM plans WHERE name = %s", (plan_name,))
            plan = cur.fetchone()
            if not plan:
                logger.error("Plan '%s' not found in DB", plan_name)
                return
            plan_id = plan["id"]

            cur.execute(
                "UPDATE workspaces SET plan_id = %s WHERE id = %s",
                (plan_id, workspace_id),
            )
            if stripe_sub_id:
                cur.execute(
                    """
                    INSERT INTO subscriptions (workspace_id, plan_id, status, stripe_subscription_id)
                    VALUES (%s, %s, 'active', %s)
                    ON CONFLICT (workspace_id)
                    DO UPDATE SET plan_id = EXCLUDED.plan_id,
                                  status = 'active',
                                  stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                                  updated_at = NOW()
                    """,
                    (workspace_id, plan_id, stripe_sub_id),
                )
            conn.commit()
            logger.info("Workspace %s upgraded to plan '%s'", workspace_id, plan_name)
    except Exception as exc:
        conn.rollback()
        logger.error("update_workspace_plan error: %s", exc)
    finally:
        release_db_connection(conn)


async def handle_stripe_event(event: dict):
    """Handle inbound Stripe webhook events."""
    if not _stripe_enabled():
        return

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        workspace_id = data.get("metadata", {}).get("workspace_id")
        plan_name    = data.get("metadata", {}).get("plan")
        sub_id       = data.get("subscription")
        if workspace_id and plan_name:
            await update_workspace_plan(workspace_id, plan_name, sub_id)

    elif event_type == "customer.subscription.deleted":
        # Downgrade to free when subscription cancelled
        sub_id = data.get("id")
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE subscriptions SET status = 'cancelled'
                        WHERE stripe_subscription_id = %s
                        """,
                        (sub_id,),
                    )
                    conn.commit()
            finally:
                release_db_connection(conn)

    else:
        logger.debug("Unhandled Stripe event: %s", event_type)
