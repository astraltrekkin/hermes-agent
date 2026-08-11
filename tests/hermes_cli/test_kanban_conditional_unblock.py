"""Regression tests for #83726 — atomic conditional kanban unblock.

Automation that observes a block event and later tries to clear only its own
block must not erase a newer block committed in between. Reason text alone is
insufficient when identical reasons can recur; callers must pin the expected
canonical ``blocked`` event id.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


@pytest.fixture
def kanban_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _latest_blocked_event_id(conn, task_id: str) -> int:
    event_id = kb.latest_blocked_event_id(conn, task_id)
    assert event_id is not None
    return event_id


def _count_events(conn, task_id: str, kind: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM task_events WHERE task_id = ? AND kind = ?",
        (task_id, kind),
    ).fetchone()
    return int(row["n"])


def test_conditional_unblock_succeeds_when_block_event_matches(kanban_home: Path) -> None:
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="match", assignee="worker")
        kb.claim_task(conn, tid)
        assert kb.block_task(conn, tid, reason="automation: capacity restored")
        event_id = _latest_blocked_event_id(conn, tid)

        assert kb.unblock_task(conn, tid, if_block_event_id=event_id) == "ok"
        assert kb.get_task(conn, tid).status == "ready"
        assert _count_events(conn, tid, "unblocked") == 1


def test_stale_conditional_unblock_preserves_newer_block(kanban_home: Path) -> None:
    """Re-block between observation and mutation must fail closed."""
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="race", assignee="worker")
        kb.claim_task(conn, tid)
        assert kb.block_task(conn, tid, reason="automation: capacity low", kind="transient")
        stale_event_id = _latest_blocked_event_id(conn, tid)

        # Another actor replaces the block before automation mutates.
        assert kb.unblock_task(conn, tid) == "ok"
        assert kb.block_task(
            conn, tid, reason="manual: approval required", kind="needs_input",
        )
        newer_event_id = _latest_blocked_event_id(conn, tid)
        assert newer_event_id != stale_event_id
        assert kb.get_task(conn, tid).status == "blocked"

        assert (
            kb.unblock_task(conn, tid, if_block_event_id=stale_event_id)
            == "condition_mismatch"
        )
        assert kb.get_task(conn, tid).status == "blocked"
        assert _latest_blocked_event_id(conn, tid) == newer_event_id
        assert _count_events(conn, tid, "unblocked") == 1


def test_conditional_unblock_mismatch_emits_no_unblocked_event(kanban_home: Path) -> None:
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="no-audit", assignee="worker")
        kb.claim_task(conn, tid)
        assert kb.block_task(conn, tid, reason="automation: waiting", kind="transient")
        stale_event_id = _latest_blocked_event_id(conn, tid)

        assert kb.unblock_task(conn, tid) == "ok"
        assert kb.block_task(conn, tid, reason="manual: hold", kind="needs_input")

        unblocked_before = _count_events(conn, tid, "unblocked")
        assert (
            kb.unblock_task(conn, tid, if_block_event_id=stale_event_id)
            == "condition_mismatch"
        )
        assert _count_events(conn, tid, "unblocked") == unblocked_before


def test_unconditional_unblock_unchanged(kanban_home: Path) -> None:
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="legacy", assignee="worker")
        kb.claim_task(conn, tid)
        assert kb.block_task(conn, tid, reason="generic block")

        assert kb.unblock_task(conn, tid) == "ok"
        assert kb.get_task(conn, tid).status == "ready"


def test_conditional_unblock_not_blocked_returns_not_blocked(kanban_home: Path) -> None:
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="ready-task", assignee="worker")
        assert kb.unblock_task(conn, tid, if_block_event_id=999) == "not_blocked"
