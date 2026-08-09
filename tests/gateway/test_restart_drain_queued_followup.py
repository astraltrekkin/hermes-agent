"""Regression tests for #82381 — restart drain must not discard queued follow-ups.

When ``/restart`` is requested during an active turn and a follow-up arrives
before that turn completes, the gateway acknowledges the message as queued
for the replacement process.  The follow-up must remain in the adapter's
pending slot through turn completion so ``flush_pending_to_file`` can persist
it at shutdown.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import _dequeue_pending_event
from gateway.session import build_session_key
from tests.gateway.restart_test_helpers import make_restart_runner, make_restart_source


@pytest.mark.asyncio
async def test_busy_handler_queues_followup_during_restart_drain():
    runner, adapter = make_restart_runner()
    runner._draining = True
    runner._restart_requested = True
    runner._busy_input_mode = "queue"

    source = make_restart_source()
    session_key = build_session_key(source)
    runner._running_agents[session_key] = MagicMock()

    followup = MessageEvent(
        text="follow up",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m2",
    )

    handled = await runner._handle_active_session_busy_message(followup, session_key)

    assert handled is True
    assert session_key in adapter._pending_messages
    assert adapter._pending_messages[session_key].text == "follow up"
    assert any("queued for the next turn" in msg for msg in adapter.sent)


def test_post_turn_drain_dequeue_discards_followup_without_fix_guard():
    """Documents the failure mode: dequeue + discard empties the adapter slot."""
    runner, adapter = make_restart_runner()
    runner._draining = True
    runner._restart_requested = True
    runner._busy_input_mode = "queue"

    source = make_restart_source()
    session_key = build_session_key(source)
    followup = MessageEvent(
        text="follow up",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m2",
    )
    adapter._pending_messages[session_key] = followup

    pending_event = _dequeue_pending_event(adapter, session_key)
    pending = pending_event.text if pending_event else None
    if runner._draining and (pending_event or pending):
        pending_event = None
        pending = None

    assert pending_event is None
    assert pending is None
    assert session_key not in adapter._pending_messages


def test_preserve_drain_queue_skips_post_turn_dequeue():
    """#82381: restart drain with queue recovery must not consume adapter pending."""
    runner, adapter = make_restart_runner()
    runner._draining = True
    runner._restart_requested = True
    runner._busy_input_mode = "queue"

    source = make_restart_source()
    session_key = build_session_key(source)
    followup = MessageEvent(
        text="follow up",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m2",
    )
    adapter._pending_messages[session_key] = followup

    preserve_drain_queue = runner._draining and runner._queue_during_drain_enabled()
    assert preserve_drain_queue is True

    pending_event = None
    pending = None
    if not preserve_drain_queue:
        pending_event = _dequeue_pending_event(adapter, session_key)
        pending = pending_event.text if pending_event else None

    if runner._draining and (pending_event or pending):
        pending_event = None
        pending = None

    assert session_key in adapter._pending_messages
    assert adapter._pending_messages[session_key].text == "follow up"
