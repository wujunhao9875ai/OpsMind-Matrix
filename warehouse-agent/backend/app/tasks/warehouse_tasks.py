"""库房管理 Celery 定时任务

- 库存阈值监控（每30分钟）
- 呆滞设备检查（每天1:00）
- 损坏设备周报（每周一9:00）
- 维修超时检查（每天8:00）
- 备件申请扫描（每30秒）
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import select, func, and_
from app.tasks.celery_app import celery_app
from app.database import async_session
from app.models.inventory import Inventory
from app.models.device import Device
from app.models.device_log import DeviceLog
from app.models.spare_part_request import SparePartRequest

logger = logging.getLogger(__name__)


async def _check_inventory_threshold_async():
    """检查库存阈值，记录低库存告警"""
    async with async_session() as db:
        result = await db.execute(
            select(Inventory).where(Inventory.quantity <= Inventory.min_threshold)
        )
        low_stock = result.scalars().all()

        for inv in low_stock:
            if inv.quantity == 0:
                logger.warning(f"库存耗尽: {inv.name} (ID: {inv.id})")
            else:
                logger.info(f"低库存: {inv.name} 剩余 {inv.quantity}，阈值 {inv.min_threshold}")

        if low_stock:
            logger.info(f"库存阈值检查完成: {len(low_stock)} 项低库存/耗尽")
        return len(low_stock)


async def _check_idle_devices_async():
    """检查呆滞设备（在库超过180天）"""
    threshold_date = datetime.now(timezone.utc) - timedelta(days=180)
    async with async_session() as db:
        result = await db.execute(
            select(Device).where(
                and_(
                    Device.status == "in_stock",
                    Device.created_at < threshold_date,
                )
            )
        )
        idle_devices = result.scalars().all()

        if idle_devices:
            logger.info(f"呆滞设备检查: {len(idle_devices)} 台设备在库超过180天")
            for d in idle_devices:
                logger.info(f"  呆滞设备: {d.device_no} {d.name} (入库: {d.created_at.date()})")
        return len(idle_devices)


async def _weekly_damaged_report_async():
    """生成本周损坏设备报告"""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    async with async_session() as db:
        result = await db.execute(
            select(Device).where(
                and_(
                    Device.status == "damaged",
                    Device.updated_at >= week_start,
                )
            )
        )
        damaged = result.scalars().all()

        if damaged:
            logger.info(f"本周损坏设备报告: {len(damaged)} 台")
            for d in damaged:
                logger.info(f"  损坏设备: {d.device_no} {d.name} {d.model} - 购入价格: {d.purchase_price}")
        return len(damaged)


async def _check_repair_overdue_async():
    """检查维修超时设备"""
    today = date.today()
    async with async_session() as db:
        result = await db.execute(
            select(DeviceLog).where(
                and_(
                    DeviceLog.action == "send_repair",
                    DeviceLog.expected_return_date < today,
                )
            )
        )
        overdue_logs = result.scalars().all()

        if overdue_logs:
            logger.info(f"维修超时提醒: {len(overdue_logs)} 台设备送修超时")
            for log in overdue_logs:
                logger.info(f"  设备 {log.device_id} 预计 {log.expected_return_date} 返还，已超时")
        return len(overdue_logs)


async def _sync_spare_requests_async():
    """扫描库存低阈值，记录告警（无外部依赖版本）"""
    async with async_session() as db:
        result = await db.execute(
            select(Inventory).where(Inventory.quantity <= Inventory.min_threshold)
        )
        low_inventory = result.scalars().all()

        if low_inventory:
            logger.info(f"低库存扫描: {len(low_inventory)} 项库存低于阈值")
        return len(low_inventory)


# ---- Celery 任务注册 ----

@celery_app.task(name="check_inventory_threshold")
def check_inventory_threshold():
    asyncio.run(_check_inventory_threshold_async())


@celery_app.task(name="check_idle_devices")
def check_idle_devices():
    asyncio.run(_check_idle_devices_async())


@celery_app.task(name="weekly_damaged_report")
def weekly_damaged_report():
    asyncio.run(_weekly_damaged_report_async())


@celery_app.task(name="check_repair_overdue")
def check_repair_overdue():
    asyncio.run(_check_repair_overdue_async())


@celery_app.task(name="sync_spare_requests")
def sync_spare_requests():
    asyncio.run(_sync_spare_requests_async())