from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo

from ...logging_config import logger
from ...utils.timezones import convert_to_user_timezone, now_in_user_timezone, resolve_user_timezone
from .models import TriggerRecord
from .store import TriggerStore
from .utils import (
    build_recurrence,
    load_rrule,
    normalize_status,
)


MISSED_TRIGGER_GRACE_PERIOD = timedelta(minutes=5)
logger = logging.getLogger("TriggerService")


class TriggerService:
    """High-level trigger management with recurrence awareness."""

    def __init__(self, store: TriggerStore):
        self._store = store

    def create_trigger(
        self,
        *,
        agent_name: str,
        payload: str,
        recurrence_rule: Optional[str] = None,
        start_time: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> TriggerRecord:
        """Create a trigger.
        
        The start_time parameter is interpreted in the user's timezone (or timezone_name if provided).
        """
        tz = resolve_user_timezone()
        
        now = now_in_user_timezone()
        start_dt_local = start_time if start_time else now
        stored_recurrence = build_recurrence(recurrence_rule, start_dt_local, tz)
        next_fire = self._compute_next_fire(
            stored_recurrence=stored_recurrence,
            start_dt_local=start_dt_local,
            tz=tz,
            now=now,
        )
        record: Dict[str, Any] = {
            "agent_name": agent_name,
            "payload": payload,
            "start_time": start_dt_local,
            "next_trigger": next_fire,
            "recurrence_rule": stored_recurrence,
            "timezone": getattr(tz, "key", "UTC"),
            "status": normalize_status(status),
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        trigger_id = self._store.insert(record)
        created = self._store.fetch_one(trigger_id, agent_name)
        if not created:  # pragma: no cover - defensive
            raise RuntimeError("Failed to load trigger after insert")
        return created

    def update_trigger(
        self,
        trigger_id: int,
        *,
        agent_name: str,
        payload: Optional[str] = None,
        recurrence_rule: Optional[str] = None,
        start_time: Optional[datetime] = None,
        status: Optional[str] = None,
        last_error: Optional[str] = None,
        clear_error: bool = False,
    ) -> Optional[TriggerRecord]:
        """Update a trigger.
        
        The start_time parameter is interpreted in the user's timezone (or timezone_name if provided).
        """
        existing = self._store.fetch_one(trigger_id, agent_name)
        if existing is None:
            return None

        tz = resolve_user_timezone()
        # existing.start_time is now a datetime in user timezone
        start_reference = (
            existing.start_time
            if existing.start_time
            else now_in_user_timezone()
        )
        
        start_dt_local = start_time if start_time else start_reference

        fields: Dict[str, Any] = {}
        if payload is not None:
            fields["payload"] = payload

        normalized_status = None
        status_changed_to_active = False
        if status is not None:
            normalized_status = normalize_status(status)
            fields["status"] = normalized_status
            status_changed_to_active = (
                normalized_status == "active" and existing.status != "active"
            )
        else:
            normalized_status = existing.status

        if start_time is not None:
            fields["start_time"] = start_dt_local
        if getattr(tz, "key", "UTC") != existing.timezone:
            fields["timezone"] = getattr(tz, "key", "UTC")

        schedule_inputs_changed = any(
            value is not None for value in (recurrence_rule, start_time, fields.get("timezone", None))
        )

        recurrence_source = (
            recurrence_rule if recurrence_rule is not None else existing.recurrence_rule
        )
        if schedule_inputs_changed:
            stored_recurrence = (
                build_recurrence(recurrence_source, start_dt_local, tz)
                if recurrence_source
                else None
            )
        else:
            stored_recurrence = recurrence_source

        # existing.next_trigger is now a datetime in user timezone
        next_trigger_dt = existing.next_trigger
        now = now_in_user_timezone()
        should_recompute_schedule = schedule_inputs_changed

        if status_changed_to_active:
            if next_trigger_dt is None:
                should_recompute_schedule = True
            else:
                missed_duration = now - next_trigger_dt
                if missed_duration > MISSED_TRIGGER_GRACE_PERIOD:
                    should_recompute_schedule = True

        if should_recompute_schedule:
            next_fire = self._compute_next_fire(
                stored_recurrence=stored_recurrence,
                start_dt_local=start_dt_local,
                tz=tz,
                now=now,
            )
            if (
                stored_recurrence is None
                and recurrence_rule is None
                and start_time is None
                and status_changed_to_active
                and next_fire is not None
                and next_fire <= now
            ):
                next_fire = now
            fields["next_trigger"] = next_fire
            if schedule_inputs_changed:
                fields["recurrence_rule"] = stored_recurrence
        elif schedule_inputs_changed:
            fields["recurrence_rule"] = stored_recurrence

        if clear_error:
            fields["last_error"] = None
        elif last_error is not None:
            fields["last_error"] = last_error

        if not fields:
            return existing

        updated = self._store.update(trigger_id, agent_name, fields)
        return self._store.fetch_one(trigger_id, agent_name) if updated else existing

    def list_triggers(self, *, agent_name: str) -> List[TriggerRecord]:
        return self._store.list_for_agent(agent_name)

    def get_due_triggers(
        self, *, before: datetime, agent_name: Optional[str] = None
    ) -> List[TriggerRecord]:
        """Get triggers due before the given datetime.
        
        The before parameter is interpreted in the user's timezone.
        """
        # Ensure before is in user timezone
        if before.tzinfo is None:
            tz = resolve_user_timezone()
            before = before.replace(tzinfo=tz)
        else:
            before = convert_to_user_timezone(before)
        return self._store.fetch_due(agent_name, before)

    def mark_as_completed(self, trigger_id: int, *, agent_name: str) -> None:
        self._store.update(
            trigger_id,
            agent_name,
            {
                "status": "completed",
                "next_trigger": None,
                "last_error": None,
            },
        )

    def schedule_next_occurrence(
        self,
        trigger: TriggerRecord,
        *,
        fired_at: datetime,
    ) -> Optional[TriggerRecord]:
        """Schedule the next occurrence of a trigger.
        
        The fired_at parameter is interpreted in the user's timezone.
        """
        if not trigger.recurrence_rule:
            self.mark_as_completed(trigger.id, agent_name=trigger.agent_name)
            return self._store.fetch_one(trigger.id, trigger.agent_name)

        # Ensure fired_at is in user timezone
        tz = resolve_user_timezone()
        if fired_at.tzinfo is None:
            fired_at = fired_at.replace(tzinfo=tz)
        else:
            fired_at = convert_to_user_timezone(fired_at)

        next_fire = self._compute_next_after(trigger.recurrence_rule, fired_at, tz)
        fields: Dict[str, Any] = {
            "next_trigger": next_fire,
            "last_error": None,
        }
        if next_fire is None:
            fields["status"] = "completed"
        self._store.update(trigger.id, trigger.agent_name, fields)
        return self._store.fetch_one(trigger.id, trigger.agent_name)

    def record_failure(self, trigger: TriggerRecord, error: str) -> None:
        self._store.update(
            trigger.id,
            trigger.agent_name,
            {
                "last_error": error,
            },
        )

    def clear_next_fire(self, trigger_id: int, *, agent_name: str) -> Optional[TriggerRecord]:
        self._store.update(
            trigger_id,
            agent_name,
            {
                "next_trigger": None,
            },
        )
        return self._store.fetch_one(trigger_id, agent_name)

    def clear_all(self) -> None:
        self._store.clear_all()
        logger.info("Cleared all triggers")

    def _compute_next_fire(
        self,
        *,
        stored_recurrence: Optional[str],
        start_dt_local: datetime,
        tz: ZoneInfo,
        now: datetime,
    ) -> Optional[datetime]:
        if stored_recurrence:
            rule = load_rrule(stored_recurrence)
            next_occurrence = rule.after(now.astimezone(tz), inc=True)
            if next_occurrence is None:
                return None
            if next_occurrence.tzinfo is None:
                next_occurrence = next_occurrence.replace(tzinfo=tz)
            return next_occurrence.astimezone(tz)

        if start_dt_local < now.astimezone(tz):
            logger.warning(
                "start_time in the past; trigger will fire immediately",
                extra={"start_time": start_dt_local.isoformat()},
            )
        return start_dt_local

    def _compute_next_after(
        self,
        stored_recurrence: str,
        fired_at: datetime,
        tz: ZoneInfo,
    ) -> Optional[datetime]:
        rule = load_rrule(stored_recurrence)
        next_occurrence = rule.after(fired_at.astimezone(tz), inc=False)
        if next_occurrence is None:
            return None
        if next_occurrence.tzinfo is None:
            next_occurrence = next_occurrence.replace(tzinfo=tz)
        return next_occurrence.astimezone(tz)


__all__ = ["TriggerService", "MISSED_TRIGGER_GRACE_PERIOD"]
