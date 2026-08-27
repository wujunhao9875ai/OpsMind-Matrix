import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.core.dispatch_engine import (
    _jaccard_similarity,
    _infer_required_skills,
    calculate_score,
)


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        assert _jaccard_similarity({"a", "b"}, {"b", "c"}) == 1.0 / 3.0

    def test_empty_sets(self):
        assert _jaccard_similarity(set(), set()) == 0.0


class TestInferRequiredSkills:
    def test_hardware_category(self):
        ticket = MagicMock()
        ticket.fault_category = "hardware"
        ticket.device_info = {"type": "printer"}
        skills = _infer_required_skills(ticket)
        assert "printer" in skills
        assert "hardware" in skills

    def test_network_category(self):
        ticket = MagicMock()
        ticket.fault_category = "network"
        ticket.device_info = {}
        skills = _infer_required_skills(ticket)
        assert "network" in skills


class TestCalculateScore:
    def test_perfect_match(self):
        engineer = MagicMock()
        engineer.skills = ["printer", "hardware"]
        engineer.current_load = 0
        engineer.max_concurrent = 5
        engineer.total_completed = 100
        engineer.rating = 5.0
        engineer.location = "5楼"

        ticket = MagicMock()
        ticket.fault_category = "hardware"
        ticket.device_info = {"type": "printer"}
        ticket.location = "5楼"

        all_engineers = [engineer]
        score = calculate_score(engineer, ticket, all_engineers)
        assert 0.8 <= score <= 1.0

    def test_no_match(self):
        engineer = MagicMock()
        engineer.skills = ["network"]
        engineer.current_load = 5
        engineer.max_concurrent = 5
        engineer.total_completed = 10
        engineer.rating = 3.0
        engineer.location = "10楼"

        ticket = MagicMock()
        ticket.fault_category = "hardware"
        ticket.device_info = {"type": "printer"}
        ticket.location = "1楼"

        all_engineers = [engineer]
        score = calculate_score(engineer, ticket, all_engineers)
        assert score < 0.5