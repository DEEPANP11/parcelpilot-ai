"""Action tool — prepare, confirm, execute with idempotency + audit."""
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.data.database import get_session, Escalation, AuditLog


SNAPSHOT_TZ = timezone(timedelta(hours=5, minutes=30))


def _now_iso():
    return datetime.now(SNAPSHOT_TZ).isoformat()


class ActionTool:
    """Tool for state-changing actions with confirmation workflow."""

    def __init__(self):
        self._pending_actions = {}  # action_id -> prepared action

    def prepare(self, action_type: str, params: dict, user_ctx) -> dict:
        """Prepare an action and return confirmation request.

        Args:
            action_type: escalation | ticket_update | followup_task
            params: Action parameters
            user_ctx: Authenticated user context
        """
        action_id = str(uuid.uuid4())[:8]
        idempotency_key = f"{action_type}_{params.get('ticket_id', 'none')}_{_now_iso()[:10]}"

        # Check for duplicate
        session = get_session()
        try:
            existing = session.query(Escalation).filter(
                Escalation.idempotency_key == idempotency_key
            ).first()
            if existing:
                return {
                    "status": "duplicate",
                    "message": f"Action already executed: {existing.escalation_id}",
                    "action_id": existing.escalation_id,
                }
        finally:
            session.close()

        if action_type == "escalation":
            prepared = self._prepare_escalation(action_id, params, user_ctx, idempotency_key)
        elif action_type == "ticket_update":
            prepared = self._prepare_ticket_update(action_id, params, user_ctx, idempotency_key)
        elif action_type == "followup_task":
            prepared = self._prepare_followup(action_id, params, user_ctx, idempotency_key)
        else:
            return {"error": f"Unknown action type: {action_type}"}

        self._pending_actions[action_id] = prepared

        return {
            "status": "awaiting_confirmation",
            "action_id": action_id,
            "action_type": action_type,
            "details": prepared["confirmation_message"],
            "message": f"Do you want me to proceed with this {action_type}?",
        }

    def confirm(self, action_id: str, confirmed: bool) -> dict:
        """Confirm or cancel a prepared action.

        Args:
            action_id: ID of the prepared action
            confirmed: Whether user confirmed
        """
        if action_id not in self._pending_actions:
            return {"error": f"No pending action found for {action_id}"}

        action = self._pending_actions.pop(action_id)

        if not confirmed:
            return {
                "status": "cancelled",
                "action_id": action_id,
                "message": "Action cancelled by user.",
            }

        # Execute
        return self._execute(action)

    def _prepare_escalation(self, action_id, params, user_ctx, idempotency_key):
        ticket_id = params.get("ticket_id", "unknown")
        severity = params.get("severity", "P2")
        reason = params.get("reason", "Customer request")

        return {
            "action_id": action_id,
            "action_type": "escalation",
            "params": params,
            "user_ctx": user_ctx,
            "idempotency_key": idempotency_key,
            "confirmation_message": {
                "ticket_id": ticket_id,
                "severity": severity,
                "reason": reason,
                "target": "Support escalation queue",
                "created_by": user_ctx.user_id,
            },
        }

    def _prepare_ticket_update(self, action_id, params, user_ctx, idempotency_key):
        return {
            "action_id": action_id,
            "action_type": "ticket_update",
            "params": params,
            "user_ctx": user_ctx,
            "idempotency_key": idempotency_key,
            "confirmation_message": params,
        }

    def _prepare_followup(self, action_id, params, user_ctx, idempotency_key):
        return {
            "action_id": action_id,
            "action_type": "followup_task",
            "params": params,
            "user_ctx": user_ctx,
            "idempotency_key": idempotency_key,
            "confirmation_message": params,
        }

    def _execute(self, action: dict) -> dict:
        """Execute a confirmed action."""
        session = get_session()
        try:
            if action["action_type"] == "escalation":
                return self._execute_escalation(session, action)
            elif action["action_type"] == "ticket_update":
                return self._execute_ticket_update(session, action)
            elif action["action_type"] == "followup_task":
                return self._execute_followup(session, action)
            else:
                return {"error": "Unknown action type"}
        finally:
            session.close()

    def _execute_escalation(self, session, action):
        params = action["params"]
        escalation_id = f"ESC-{action['action_id'].upper()}"

        escalation = Escalation(
            escalation_id=escalation_id,
            ticket_id=params.get("ticket_id", "unknown"),
            account_id=params.get("account_id", "unknown"),
            severity=params.get("severity", "P2"),
            reason=params.get("reason", "Customer request"),
            created_by=action["user_ctx"].user_id,
            created_at=_now_iso(),
            status="active",
            idempotency_key=action["idempotency_key"],
        )
        session.add(escalation)
        session.commit()

        # Audit log
        self._log_audit(session, action, f"Created escalation {escalation_id}")

        return {
            "status": "executed",
            "action_type": "escalation",
            "escalation_id": escalation_id,
            "message": f"Escalation {escalation_id} created successfully.",
        }

    def _execute_ticket_update(self, session, action):
        self._log_audit(session, action, "Ticket updated")
        return {
            "status": "executed",
            "action_type": "ticket_update",
            "message": "Ticket updated successfully.",
        }

    def _execute_followup(self, session, action):
        self._log_audit(session, action, "Follow-up task created")
        return {
            "status": "executed",
            "action_type": "followup_task",
            "message": "Follow-up task created successfully.",
        }

    def _log_audit(self, session, action, result):
        log = AuditLog(
            timestamp=_now_iso(),
            session_id=action.get("action_id"),
            user_id=action["user_ctx"].user_id,
            account_id=action["user_ctx"].account_id,
            action=action["action_type"],
            tool_calls=json.dumps([action["params"]]),
            result=result,
        )
        session.add(log)
        session.commit()
