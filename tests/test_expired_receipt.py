"""Original prepared requests resume from their Host receipt after media expiry."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from yuki_plugin_sdk.models import NotificationPublishReceipt
from yuki_plugin_sdk.testing import FakePluginContext

from github_monitor import polling
from github_monitor.config import NotificationTargetConfig, RepositorySubscription
from github_monitor.models import (
    ActivationState,
    DeliveryUnit,
    NormalizedGitHubEvent,
    PreparedMedia,
    QueuedSourceEvent,
    QueueState,
    TargetDelivery,
    build_prepared_notification,
    delivery_target_key,
)
from github_monitor.polling import GitHubPoller
from github_monitor.state import QUEUE_NAMESPACE, load_queue_state

NOW = datetime(2026, 10, 19, tzinfo=UTC)
TARGET_ID = "dd0a3065-9ebd-4082-958a-1ff4de3ff536"


@pytest.mark.parametrize("activation", [False, True])
async def test_attempting_delivery_keeps_original_request_after_expiry_and_target_removal(
    monkeypatch, activation
):
    context = FakePluginContext("github-monitor")
    prepared = build_prepared_notification(
        event_key="original-activation" if activation else "github:owner/repo:event:100",
        event_type="monitor_enabled" if activation else "WatchEvent",
        target_type="group",
        target_id=TARGET_ID,
        conversation_id="ca76e17d-5629-4375-8c97-d10d4df38b3d",
        occurred_at=NOW,
        summary="Original accepted notification",
        payload={"repository": "owner/repo", "event_id": "100"},
        text="original text",
        media=(PreparedMedia(index=0, handle_id="original-card", sha256="b" * 64, expires_at=NOW),),
    )
    delivery = TargetDelivery(
        target_key=delivery_target_key("group", TARGET_ID, prepared.conversation_id),
        target_type="group",
        target_id=TARGET_ID,
        conversation_id=prepared.conversation_id,
        send_text=True,
        send_card=True,
        ask_agent=False,
        status="attempting",
        prepared=prepared,
        notification_id="original-notification",
        source_event_id=41,
    )
    if activation:
        queue = QueueState(
            activation=ActivationState(
                activation_id="original-activation", occurred_at=NOW, deliveries=(delivery,)
            )
        )
    else:
        event = NormalizedGitHubEvent(
            github_event_id="100",
            repository="owner/repo",
            event_type="WatchEvent",
            actor="alice",
            created_at=NOW,
            summary=prepared.summary,
            event_key=prepared.event_key,
        )
        source = QueuedSourceEvent(
            github_event_id="100",
            source_fingerprint="a" * 64,
            source_created_at=NOW,
            normalized=event,
        )
        queue = QueueState(
            accepted_cursor="100",
            accepted_fingerprint=source.source_fingerprint,
            inflight=DeliveryUnit(
                unit_id="original-unit", members=(source,), deliveries=(delivery,), sealed_at=NOW
            ),
        )
    await context.storage.set(QUEUE_NAMESPACE, "owner/repo", queue.model_dump(mode="json"))
    snapshot = await load_queue_state(context, "owner/repo")
    receipt = NotificationPublishReceipt(
        notification_id="original-notification",
        source_event_id=41,
        event_created=False,
        delivery_enqueued=False,
        agent_turn_enqueued=False,
        deduplicated=True,
    )
    publish = AsyncMock(return_value=receipt)
    context.notifications.publish = publish
    context.media.create_artifact = AsyncMock()
    subscription = RepositorySubscription(
        repository="owner/repo",
        targets=(NotificationTargetConfig(target_type="group", target_id="another-space"),),
    )

    class AfterDeadline(datetime):
        @classmethod
        def now(cls, tz=None):
            value = NOW + timedelta(days=8)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    monkeypatch.setattr(polling, "datetime", AfterDeadline)
    poller = GitHubPoller(context, asyncio.Event())
    drain = poller._retire_activation_target if activation else poller._drain_unit_target
    finished = await drain(subscription, snapshot, delivery.target_key)
    saved = await load_queue_state(context, "owner/repo")
    selected = saved.state.activation if activation else saved.state.inflight
    assert selected is not None
    completed = selected.deliveries[0]
    assert completed.status == "completed"
    assert completed.prepared == prepared
    assert (completed.notification_id, completed.source_event_id) == ("original-notification", 41)
    publish.assert_awaited_once_with(poller._publish_request(prepared))
    assert saved == finished
    await drain(subscription, saved, delivery.target_key)
    assert publish.await_count == 1
    context.media.create_artifact.assert_not_awaited()
    assert context.http.requests == []
