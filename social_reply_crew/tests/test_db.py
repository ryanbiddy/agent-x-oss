from social_reply_crew.db import ReplyMemoryStore
from social_reply_crew.models import ReplyMetricSnapshot


def test_build_performance_payload_uses_stored_replies(tmp_path):
    database_path = tmp_path / "memory.db"
    store = ReplyMemoryStore(database_path)
    store.initialize()

    store.record_reply(
        post_url="https://x.com/example/status/1",
        original_tweet="Original post one",
        generated_reply="Specific reply with a clear angle.",
        engagement_score=7,
    )
    store.record_reply(
        post_url="https://x.com/example/status/2",
        original_tweet="Original post two",
        generated_reply="Another reply that asks a sharp question?",
        engagement_score=3,
    )

    payload = store.build_performance_payload()

    assert payload["weighted_metrics"]["sample_count"] == 2
    assert payload["high_performing_examples"][0]["engagement_score"] == 7
    assert any("Anchor the first sentence" in rule for rule in payload["rules"])


def test_refresh_from_snapshots_updates_existing_reply(tmp_path):
    database_path = tmp_path / "memory.db"
    store = ReplyMemoryStore(database_path)
    store.initialize()

    store.record_reply(
        post_url="https://x.com/example/status/3",
        original_tweet="Original post three",
        generated_reply="Compact reply text for matching.",
        engagement_score=0,
    )

    report = store.refresh_from_snapshots(
        [
            ReplyMetricSnapshot(
                reply_text="Compact reply text for matching.",
                likes=4,
                retweets=1,
            )
        ]
    )

    recent_reply = store.get_recent_replies(limit=1)[0]

    assert report.scanned_replies == 1
    assert report.matched_rows == 1
    assert report.updated_rows == 1
    assert recent_reply.engagement_score == 5
