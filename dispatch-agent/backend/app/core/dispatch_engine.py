import logging
import re
from sqlalchemy import select
from app.database import async_session
from app.models.engineer import EngineerProfile
from app.models.ticket import Ticket
from app.config import settings

logger = logging.getLogger(__name__)


def _extract_floor_number(location: str | None) -> int | None:
    """Extract floor number from location string like '5楼', '3层', 'B1楼'."""
    if not location:
        return None
    # Handle negative/B floors
    match = re.search(r"[Bb](\d+)", location)
    if match:
        return -int(match.group(1))
    # Handle regular floors
    match = re.search(r"(\d+)\s*[楼层层Ff]", location)
    if match:
        return int(match.group(1))
    return None


def _location_proximity_score(engineer: EngineerProfile, ticket: Ticket) -> float:
    """Calculate location proximity score.
    - Engineer at same location as ticket: 1.0
    - Engineer at same floor: 0.9
    - Adjacent floors (1-2 floors diff): 0.7
    - Same building (3-5 floors diff): 0.5
    - Different building: 0.1
    - Unknown location: 0.3 (neutral)
    """
    ticket_loc = ticket.location
    eng_loc = engineer.location or engineer.last_location

    if not ticket_loc or not eng_loc:
        return 0.3

    # Same location string
    if ticket_loc.strip() == eng_loc.strip():
        return 1.0

    ticket_floor = _extract_floor_number(ticket_loc)
    eng_floor = _extract_floor_number(eng_loc)

    if ticket_floor is not None and eng_floor is not None:
        diff = abs(ticket_floor - eng_floor)
        if diff == 0:
            return 0.9
        elif diff <= 2:
            return 0.7
        elif diff <= 5:
            return 0.5
        return 0.1

    return 0.3


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _infer_required_skills(ticket: Ticket) -> set:
    """Infer required skill tags from ticket."""
    skills = set()
    category_skill_map = {
        "hardware": {"printer", "computer", "hardware"},
        "software": {"software", "system", "app"},
        "network": {"network", "wifi", "vpn"},
        "other": set(),
    }
    skills.update(category_skill_map.get(ticket.fault_category, set()))
    if ticket.device_info and isinstance(ticket.device_info, dict):
        device_type = ticket.device_info.get("type", "")
        if device_type:
            skills.add(device_type)
    return skills


def calculate_score(engineer: EngineerProfile, ticket: Ticket, all_engineers: list[EngineerProfile]) -> float:
    required_skills = _infer_required_skills(ticket)
    engineer_skills = set(engineer.skills) if engineer.skills else set()

    skill_score = _jaccard_similarity(required_skills, engineer_skills)
    load_ratio = engineer.current_load / max(engineer.max_concurrent, 1)
    load_score = 1.0 - min(load_ratio, 1.0)

    avg_load = sum(e.current_load for e in all_engineers) / max(len(all_engineers), 1)
    balance_score = 1.0 - abs(engineer.current_load - avg_load) / max(engineer.max_concurrent, 1)
    balance_score = max(0.0, min(1.0, balance_score))

    max_completed = max((e.total_completed for e in all_engineers), default=1)
    performance_score = (engineer.total_completed / max(max_completed, 1) + engineer.rating / 5.0) / 2.0

    location_score = _location_proximity_score(engineer, ticket)

    total = (
        settings.dispatch_skill_weight * skill_score
        + settings.dispatch_load_weight * load_score
        + settings.dispatch_balance_weight * balance_score
        + settings.dispatch_performance_weight * performance_score
        + settings.dispatch_location_weight * location_score
    )
    return round(total, 4)


async def find_best_engineer(ticket: Ticket) -> EngineerProfile | None:
    async with async_session() as db:
        result = await db.execute(
            select(EngineerProfile).where(EngineerProfile.status.in_(["available", "online"]))
        )
        candidates = result.scalars().all()

        if not candidates:
            return None

        required_skills = _infer_required_skills(ticket)
        # Filter: skill match (skip if no required skills inferred)
        if required_skills:
            candidates = [e for e in candidates if set(e.skills or []) & required_skills]
            if not candidates:
                return None

        # Filter: not overloaded
        candidates = [e for e in candidates if e.current_load < e.max_concurrent]
        if not candidates:
            return None

        # Score and sort (candidates is the filtered pool for balance calculation)
        scored = [(e, calculate_score(e, ticket, candidates)) for e in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0] if scored else None