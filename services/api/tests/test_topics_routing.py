"""
Unit tests for the topics Lambda handler — routing and validation only.
No AWS calls are made; DynamoDB/SFN/Scheduler interactions are tested
in the Jupyter notebook against the real dev account.
"""
import json
import sys
import os

# Add services/api and packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../packages"))

# Set required env vars before importing the handler
os.environ.setdefault("DYNAMODB_TABLE_NAME", "ebook-platform-dev")
os.environ.setdefault("STEP_FUNCTIONS_ARN", "arn:aws:states:us-east-1:123456789012:stateMachine:test")
os.environ.setdefault("AWS_REGION_NAME", "us-east-1")

import pytest
from topics import _match_route, _parse_body


# ── Route matching tests ──────────────────────────────────────────────────────


class TestRouteMatching:
    def test_list_topics(self):
        handler, params = _match_route("GET", "/admin/topics")
        assert handler is not None
        assert params == {}

    def test_create_topic(self):
        handler, params = _match_route("POST", "/admin/topics")
        assert handler is not None

    def test_reorder_before_parameterised(self):
        # /admin/topics/reorder must match the exact route, not {topicId}
        handler, params = _match_route("PUT", "/admin/topics/reorder")
        assert handler is not None
        assert params == {}

    def test_get_topic(self):
        handler, params = _match_route("GET", "/admin/topics/abc-123")
        assert handler is not None
        assert params == {"topicId": "abc-123"}

    def test_update_topic(self):
        handler, params = _match_route("PUT", "/admin/topics/abc-123")
        assert handler is not None
        assert params == {"topicId": "abc-123"}

    def test_delete_topic(self):
        handler, params = _match_route("DELETE", "/admin/topics/abc-123")
        assert handler is not None
        assert params == {"topicId": "abc-123"}

    def test_trigger_run(self):
        handler, params = _match_route("POST", "/admin/topics/abc-123/trigger")
        assert handler is not None
        assert params == {"topicId": "abc-123"}

    def test_unknown_route_returns_none(self):
        handler, params = _match_route("GET", "/admin/unknown")
        assert handler is None


# ── Body parsing tests ────────────────────────────────────────────────────────


class TestParseBody:
    def test_string_body(self):
        event = {"body": '{"title": "Test"}'}
        assert _parse_body(event) == {"title": "Test"}

    def test_dict_body(self):
        event = {"body": {"title": "Test"}}
        assert _parse_body(event) == {"title": "Test"}

    def test_missing_body(self):
        event = {}
        assert _parse_body(event) == {}

    def test_null_body(self):
        event = {"body": None}
        assert _parse_body(event) == {}


# ── Validation tests (pure Pydantic, no AWS) ─────────────────────────────────


class TestTopicCreateValidation:
    def test_valid_minimal(self):
        from shared_types.models import TopicCreate
        t = TopicCreate(title="Test", description="A test description here.", instructions="Be concise.")
        assert t.schedule_type.value == "manual"
        assert t.subtopics == []

    def test_title_too_short(self):
        from pydantic import ValidationError
        from shared_types.models import TopicCreate
        with pytest.raises(ValidationError):
            TopicCreate(title="AB", description="Valid description here.", instructions="Valid instruction here.")

    def test_custom_schedule_requires_cron(self):
        from pydantic import ValidationError
        from shared_types.models import TopicCreate, ScheduleType
        with pytest.raises(ValidationError):
            TopicCreate(
                title="Test topic",
                description="Valid description here.",
                instructions="Valid instruction here.",
                schedule_type=ScheduleType.custom,
                cron_expression=None,
            )

    def test_custom_schedule_with_cron(self):
        from shared_types.models import TopicCreate, ScheduleType
        t = TopicCreate(
            title="Test topic",
            description="Valid description here.",
            instructions="Valid instruction here.",
            schedule_type=ScheduleType.custom,
            cron_expression="cron(0 9 ? * MON *)",
        )
        assert t.cron_expression == "cron(0 9 ? * MON *)"
