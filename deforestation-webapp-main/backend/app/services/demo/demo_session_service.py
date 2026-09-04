"""Demonstration session lifecycle, usage budget, and product events."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.demo.catalog import SCENARIOS
from app.core.demo.constants import (
    DEFAULT_DEMO_BUDGET,
    DEMO_SESSION_HOURS,
    GUIDE_STEPS,
)
from app.core.demo.errors import DemoBudgetError
from app.core.demo.identity import create_demo_token, demo_public_user
from app.core.errors import AuthError, ForbiddenError
from app.models.demo import (
    DemoBudgetPublic,
    DemoProductEvent,
    DemoSession,
    DemoStatusPublic,
)
from app.models.user import UserPublic


def remaining_budget(session: DemoSession) -> dict[str, int]:
    remaining: dict[str, int] = {}
    for key, limit in session.budget.items():
        used = int(session.used.get(key, 0))
        remaining[key] = max(limit - used, 0)
    return remaining


def budget_exhausted(session: DemoSession) -> bool:
    return all(value <= 0 for value in remaining_budget(session).values())


class DemoSessionService:
    def __init__(self, sessions: Any, catalog: Any) -> None:
        self._sessions = sessions
        self._catalog = catalog

    async def start(
        self, existing_session_id: str | None = None
    ) -> tuple[UserPublic, str, DemoStatusPublic]:
        """Begin a fresh demonstration: new session, or reset a live cookie session.

        ``POST /demo/start`` is a start, not a resume. Reusing an exhausted
        session id without resetting would make the first user action fail.
        """
        now = datetime.now(timezone.utc)
        if existing_session_id:
            existing = await self._sessions.find_by_id(existing_session_id)
            if existing is not None and not self._expired(existing, now=now):
                status = await self.reset(existing_session_id)
                await self.record(existing_session_id, "demo_started")
                token = create_demo_token(existing_session_id)
                user = demo_public_user(
                    existing_session_id, created_at=existing.created_at
                )
                return user, token, status

        org = await self._catalog.ensure_seeded()
        session = await self._sessions.insert(
            DemoSession(
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(hours=DEMO_SESSION_HOURS),
                budget=dict(DEFAULT_DEMO_BUDGET),
                used={key: 0 for key in DEFAULT_DEMO_BUDGET},
            )
        )
        await self.record(str(session.id), "demo_started")
        token = create_demo_token(str(session.id))
        user = demo_public_user(str(session.id), created_at=session.created_at)
        return user, token, self._status(session, org)

    @staticmethod
    def _expired(session: DemoSession, *, now: datetime | None = None) -> bool:
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires <= (now or datetime.now(timezone.utc))

    async def require(self, session_id: str) -> DemoSession:
        session = await self._sessions.find_by_id(session_id)
        if session is None:
            raise AuthError("Demonstration session is not valid")
        if self._expired(session):
            raise AuthError("Demonstration session has expired")
        await self._sessions.update(
            str(session.id),
            {"last_seen_at": datetime.now(timezone.utc)},
        )
        return session

    async def public_user(self, session_id: str) -> UserPublic:
        session = await self.require(session_id)
        return demo_public_user(str(session.id), created_at=session.created_at)

    async def status_for(self, session_id: str) -> DemoStatusPublic:
        session = await self.require(session_id)
        org = await self._catalog.ensure_seeded()
        return self._status(session, org)

    async def reset(self, session_id: str) -> DemoStatusPublic:
        session = await self.require(session_id)
        org = await self._catalog.reset_catalog()
        now = datetime.now(timezone.utc)
        await self._sessions.update(
            str(session.id),
            {
                "used": {key: 0 for key in DEFAULT_DEMO_BUDGET},
                "budget": dict(DEFAULT_DEMO_BUDGET),
                "guide_step": "forests",
                "focused_scenario": None,
                "reset_count": int(session.reset_count) + 1,
                "last_seen_at": now,
                "expires_at": now + timedelta(hours=DEMO_SESSION_HOURS),
            },
        )
        await self.record(str(session.id), "demo_reset")
        refreshed = await self.require(session_id)
        return self._status(refreshed, org)

    async def consume(self, session_id: str, meter: str, *, amount: int = 1) -> DemoSession:
        session = await self.require(session_id)
        if meter not in session.budget:
            raise ForbiddenError("Unknown demonstration action")
        used = int(session.used.get(meter, 0)) + amount
        if used > int(session.budget[meter]):
            await self.record(session_id, "demo_budget_exhausted", {"meter": meter})
            raise DemoBudgetError(
                "You've explored the ForestWatch intelligence engine. "
                "Create an organization to continue monitoring your own forests."
            )
        used_map = dict(session.used)
        used_map[meter] = used
        await self._sessions.update(
            str(session.id),
            {"used": used_map, "last_seen_at": datetime.now(timezone.utc)},
        )
        session.used = used_map
        return session

    async def set_guide_step(self, session_id: str, step_id: str) -> DemoStatusPublic:
        session = await self.require(session_id)
        known = {step["id"] for step in GUIDE_STEPS}
        if step_id not in known:
            raise ForbiddenError("Unknown demonstration step")
        await self._sessions.update(
            str(session.id),
            {"guide_step": step_id, "last_seen_at": datetime.now(timezone.utc)},
        )
        session.guide_step = step_id
        org = await self._catalog.ensure_seeded()
        return self._status(session, org)

    async def focus_scenario(self, session_id: str, scenario_id: str) -> DemoStatusPublic:
        session = await self.require(session_id)
        known = {item["id"] for item in SCENARIOS}
        if scenario_id not in known:
            raise ForbiddenError("Unknown demonstration scenario")
        await self._sessions.update(
            str(session.id),
            {
                "focused_scenario": scenario_id,
                "last_seen_at": datetime.now(timezone.utc),
            },
        )
        await self.record(session_id, "scenario_opened", {"scenario_id": scenario_id})
        session.focused_scenario = scenario_id
        org = await self._catalog.ensure_seeded()
        return self._status(session, org)

    async def record(
        self,
        session_id: str,
        event_name: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        await self._sessions.record_product_event(
            DemoProductEvent(
                session_id=session_id,
                event_name=event_name,
                detail=detail or {},
            )
        )

    def _status(self, session: DemoSession, org: Any) -> DemoStatusPublic:
        remaining = remaining_budget(session)
        return DemoStatusPublic(
            session_id=str(session.id),
            organization_id=str(org.id),
            organization_name=org.name,
            guide_step=session.guide_step,
            focused_scenario=session.focused_scenario,
            scenarios=[dict(item) for item in SCENARIOS],
            guide=[dict(item) for item in GUIDE_STEPS],
            budget=DemoBudgetPublic(
                remaining=remaining,
                limits=dict(session.budget),
                exhausted=budget_exhausted(session),
            ),
        )
