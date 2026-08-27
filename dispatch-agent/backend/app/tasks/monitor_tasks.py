import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from app.tasks.celery_app import celery_app
from app.database import async_session
from app.models.ticket import Ticket
from app.models.ticket_log import TicketLog
from app.models.urge_record import UrgeRecord
from app.models.engineer import EngineerProfile
from app.core.notification import notification_service
from app.core.dispatch_engine import find_best_engineer
from app.config import settings

logger = logging.getLogger(__name__)


async def _check_sla_breach():
    now = datetime.now(timezone.utc)
    cooldown = now - timedelta(minutes=settings.urge_cooldown_minutes)

    async with async_session() as db:
        result = await db.execute(
            select(Ticket).where(
                and_(
                    Ticket.status.in_(["assigned", "in_progress"]),
                    Ticket.sla_deadline < now,
                )
            )
        )
        overdue_tickets = result.scalars().all()

        for ticket in overdue_tickets:
            try:
                urge_result = await db.execute(
                    select(UrgeRecord).where(
                        UrgeRecord.ticket_id == ticket.id,
                        UrgeRecord.created_at >= cooldown,
                    )
                )
                if urge_result.scalar_one_or_none():
                    continue

                sla_minutes = {
                    "critical": settings.sla_critical_minutes,
                    "high": settings.sla_high_minutes,
                    "medium": settings.sla_medium_minutes,
                    "low": settings.sla_low_minutes,
                }.get(ticket.urgency, settings.sla_medium_minutes)
                overdue_minutes = int((now - ticket.sla_deadline).total_seconds() / 60)

                urge = UrgeRecord(
                    ticket_id=ticket.id,
                    urge_type="auto_timeout",
                    message=f"工单已超时 {overdue_minutes} 分钟，请尽快处理",
                )
                db.add(urge)

                if ticket.assigned_to:
                    await notification_service.notify_urge(str(ticket.assigned_to), {
                        "ticket_id": str(ticket.id),
                        "ticket_no": ticket.ticket_no,
                        "message": f"工单已超时 {overdue_minutes} 分钟，请尽快处理",
                        "overdue_minutes": overdue_minutes,
                    })

                if overdue_minutes > sla_minutes * 2:
                    await notification_service.notify_admin_alert("sla_breach", {
                        "ticket_id": str(ticket.id),
                        "ticket_no": ticket.ticket_no,
                        "title": ticket.title,
                        "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
                        "overdue_minutes": overdue_minutes,
                        "urgency": ticket.urgency,
                    })
            except Exception as e:
                logger.error(f"SLA check failed for ticket {ticket.id}: {e}")

        await db.commit()


async def _check_unassigned_pool():
    import redis.asyncio as redis
    r = redis.from_url(settings.redis_url, decode_responses=True)

    try:
        async with async_session() as db:
            while True:
                ticket_id = await r.spop("unassigned_tickets")
                if not ticket_id:
                    break
                result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
                ticket = result.scalar_one_or_none()
                if ticket and ticket.status == "created":
                    best_engineer = await find_best_engineer(ticket)
                    if best_engineer:
                        old_status = ticket.status
                        ticket.status = "assigned"
                        ticket.assigned_to = best_engineer.user_id
                        ticket.assigned_at = datetime.now(timezone.utc)
                        log = TicketLog(
                            ticket_id=ticket.id,
                            action="auto_assign",
                            from_status=old_status,
                            to_status="assigned",
                            comment=f"自动指派给工程师 {best_engineer.user_id}",
                        )
                        db.add(log)
                        await notification_service.notify_new_ticket(str(best_engineer.user_id), {
                            "ticket_id": str(ticket.id),
                            "ticket_no": ticket.ticket_no,
                            "title": ticket.title,
                            "urgency": ticket.urgency,
                        })
                    else:
                        await r.sadd("unassigned_tickets", ticket_id)
            await db.commit()
    except Exception as e:
        logger.error(f"Unassigned pool check failed: {e}")
    finally:
        await r.aclose()


async def _auto_close_tickets():
    deadline = datetime.now(timezone.utc) - timedelta(days=settings.auto_close_days)
    async with async_session() as db:
        result = await db.execute(
            select(Ticket).where(
                and_(
                    Ticket.status == "resolved",
                    Ticket.resolved_at < deadline,
                )
            )
        )
        tickets = result.scalars().all()
        for ticket in tickets:
            old_status = ticket.status
            ticket.status = "closed"
            ticket.closed_at = datetime.now(timezone.utc)
            log = TicketLog(
                ticket_id=ticket.id,
                action="auto_close",
                from_status=old_status,
                to_status="closed",
                comment="系统自动关闭（已解决超过配置天数）",
            )
            db.add(log)
        await db.commit()


async def _sync_engineer_load():
    import redis.asyncio as redis
    r = redis.from_url(settings.redis_url, decode_responses=True)

    try:
        async with async_session() as db:
            result = await db.execute(select(EngineerProfile))
            engineers = result.scalars().all()
            for engineer in engineers:
                load = await r.get(f"engineer:{engineer.user_id}:load")
                if load is not None:
                    engineer.current_load = int(load)
            await db.commit()
    except Exception as e:
        logger.error(f"Engineer load sync failed: {e}")
    finally:
        await r.aclose()


@celery_app.task(name="check_sla_breach")
def check_sla_breach():
    asyncio.run(_check_sla_breach())


@celery_app.task(name="check_unassigned_pool")
def check_unassigned_pool():
    asyncio.run(_check_unassigned_pool())


@celery_app.task(name="auto_close_tickets")
def auto_close_tickets():
    asyncio.run(_auto_close_tickets())


@celery_app.task(name="sync_engineer_load")
def sync_engineer_load():
    asyncio.run(_sync_engineer_load())