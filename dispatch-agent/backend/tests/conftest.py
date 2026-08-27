import pytest
from app.core.ticket_state_machine import (
    validate_transition,
    get_next_status,
    calculate_sla_deadline,
)


class TestValidateTransition:
    def test_created_assign_valid(self):
        assert validate_transition("created", "assign") is True

    def test_created_accept_invalid(self):
        assert validate_transition("created", "accept") is False

    def test_assigned_accept_valid(self):
        assert validate_transition("assigned", "accept") is True

    def test_assigned_reject_valid(self):
        assert validate_transition("assigned", "reject") is True

    def test_in_progress_resolve_valid(self):
        assert validate_transition("in_progress", "resolve") is True

    def test_resolved_close_valid(self):
        assert validate_transition("resolved", "close") is True

    def test_resolved_reopen_valid(self):
        assert validate_transition("resolved", "reopen") is True

    def test_closed_any_invalid(self):
        assert validate_transition("closed", "assign") is False

    def test_cancelled_any_invalid(self):
        assert validate_transition("cancelled", "assign") is False

    def test_unknown_status_invalid(self):
        assert validate_transition("unknown", "assign") is False


class TestGetNextStatus:
    def test_assign_to_assigned(self):
        assert get_next_status("created", "assign") == "assigned"

    def test_accept_to_in_progress(self):
        assert get_next_status("assigned", "accept") == "in_progress"

    def test_reject_to_created(self):
        assert get_next_status("assigned", "reject") == "created"

    def test_resolve_to_resolved(self):
        assert get_next_status("in_progress", "resolve") == "resolved"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            get_next_status("created", "accept")


class TestSlaDeadline:
    def test_critical_sla(self):
        deadline = calculate_sla_deadline("critical")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) + timedelta(minutes=120)
        diff = abs((deadline - expected).total_seconds())
        assert diff < 5

    def test_medium_sla(self):
        deadline = calculate_sla_deadline("medium")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) + timedelta(minutes=480)
        diff = abs((deadline - expected).total_seconds())
        assert diff < 5