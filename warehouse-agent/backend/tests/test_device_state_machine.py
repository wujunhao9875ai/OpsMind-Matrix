"""设备生命周期状态机单元测试"""
import pytest
import uuid
from app.core.device_state_machine import (
    DeviceStatus, DeviceAction, DEVICE_TRANSITIONS,
    get_next_status, get_available_actions,
    InvalidStateError, InvalidTransitionError,
    build_device_log, TERMINAL_STATES,
)


class TestDeviceTransitions:
    """验证状态转换表完整性"""

    def test_all_statuses_have_transitions_except_terminal(self):
        """除终态外，所有状态都应有转换规则"""
        for status in DeviceStatus:
            if status in TERMINAL_STATES:
                continue
            assert status in DEVICE_TRANSITIONS, f"状态 {status} 缺少转换规则"

    def test_terminal_has_no_transitions(self):
        """终态不应有转换规则"""
        for status in TERMINAL_STATES:
            assert status not in DEVICE_TRANSITIONS, f"终态 {status} 不应有转换规则"

    def test_all_actions_lead_to_valid_status(self):
        """所有转换的目标状态必须是合法状态"""
        valid_statuses = {s.value for s in DeviceStatus}
        for from_status, actions in DEVICE_TRANSITIONS.items():
            for action, to_status in actions.items():
                assert to_status in valid_statuses, f"{from_status} + {action} -> {to_status} 不是合法状态"


class TestGetNextStatus:
    """验证 get_next_status 正常路径"""

    def test_in_stock_to_allocated(self):
        assert get_next_status(DeviceStatus.IN_STOCK, DeviceAction.ALLOCATE) == DeviceStatus.ALLOCATED

    def test_in_stock_to_scrapped(self):
        assert get_next_status(DeviceStatus.IN_STOCK, DeviceAction.SCRAP) == DeviceStatus.SCRAPPED

    def test_allocated_to_in_use(self):
        assert get_next_status(DeviceStatus.ALLOCATED, DeviceAction.DELIVER) == DeviceStatus.IN_USE

    def test_allocated_cancel_to_in_stock(self):
        assert get_next_status(DeviceStatus.ALLOCATED, DeviceAction.CANCEL_ALLOCATE) == DeviceStatus.IN_STOCK

    def test_in_use_to_damaged(self):
        assert get_next_status(DeviceStatus.IN_USE, DeviceAction.RETURN_DAMAGED) == DeviceStatus.DAMAGED

    def test_damaged_to_in_repair(self):
        assert get_next_status(DeviceStatus.DAMAGED, DeviceAction.SEND_REPAIR) == DeviceStatus.IN_REPAIR

    def test_damaged_to_scrapped(self):
        assert get_next_status(DeviceStatus.DAMAGED, DeviceAction.SCRAP) == DeviceStatus.SCRAPPED

    def test_in_repair_to_repaired(self):
        assert get_next_status(DeviceStatus.IN_REPAIR, DeviceAction.REPAIR_DONE) == DeviceStatus.REPAIRED

    def test_repaired_to_in_stock(self):
        assert get_next_status(DeviceStatus.REPAIRED, DeviceAction.RESTOCK) == DeviceStatus.IN_STOCK

    def test_repaired_to_scrapped(self):
        assert get_next_status(DeviceStatus.REPAIRED, DeviceAction.SCRAP) == DeviceStatus.SCRAPPED


class TestGetNextStatusErrors:
    """验证 get_next_status 异常路径"""

    def test_terminal_state_raises(self):
        """终态设备不可再变更"""
        with pytest.raises(InvalidStateError, match="终态"):
            get_next_status(DeviceStatus.SCRAPPED, DeviceAction.ALLOCATE)

    def test_unknown_status_raises(self):
        """未知状态应报错"""
        with pytest.raises(InvalidStateError, match="未知状态"):
            get_next_status("non_existent", DeviceAction.ALLOCATE)

    def test_invalid_transition_raises(self):
        """非法转换应报错并提示可用操作"""
        with pytest.raises(InvalidTransitionError, match="可用操作"):
            get_next_status(DeviceStatus.IN_STOCK, DeviceAction.DELIVER)

    def test_cannot_allocate_allocated(self):
        """已分配的设备不能再次分配"""
        with pytest.raises(InvalidTransitionError):
            get_next_status(DeviceStatus.ALLOCATED, DeviceAction.ALLOCATE)

    def test_cannot_return_damaged_from_in_stock(self):
        """在库设备不能报告损坏"""
        with pytest.raises(InvalidTransitionError):
            get_next_status(DeviceStatus.IN_STOCK, DeviceAction.RETURN_DAMAGED)


class TestGetAvailableActions:
    """验证可用操作查询"""

    def test_in_stock_actions(self):
        actions = get_available_actions(DeviceStatus.IN_STOCK)
        assert DeviceAction.ALLOCATE in actions
        assert DeviceAction.SCRAP in actions
        assert len(actions) == 2

    def test_allocated_actions(self):
        actions = get_available_actions(DeviceStatus.ALLOCATED)
        assert DeviceAction.DELIVER in actions
        assert DeviceAction.CANCEL_ALLOCATE in actions

    def test_damaged_actions(self):
        actions = get_available_actions(DeviceStatus.DAMAGED)
        assert DeviceAction.SEND_REPAIR in actions
        assert DeviceAction.SCRAP in actions

    def test_terminal_returns_empty(self):
        assert get_available_actions(DeviceStatus.SCRAPPED) == []

    def test_unknown_status_returns_empty(self):
        assert get_available_actions("non_existent") == []


class TestBuildDeviceLog:
    """验证设备日志构建"""

    def test_basic_log(self):
        device_id = uuid.uuid4()
        operator_id = uuid.uuid4()
        log = build_device_log(
            device_id=device_id,
            action=DeviceAction.ALLOCATE,
            from_status=DeviceStatus.IN_STOCK,
            to_status=DeviceStatus.ALLOCATED,
            operator_id=operator_id,
        )
        assert log["device_id"] == device_id
        assert log["action"] == DeviceAction.ALLOCATE
        assert log["from_status"] == DeviceStatus.IN_STOCK
        assert log["to_status"] == DeviceStatus.ALLOCATED
        assert log["operator_id"] == operator_id
        assert log["related_ticket_id"] is None
        assert "created_at" in log

    def test_log_with_ticket(self):
        ticket_id = uuid.uuid4()
        log = build_device_log(
            device_id=uuid.uuid4(), action=DeviceAction.SEND_REPAIR,
            from_status=DeviceStatus.DAMAGED, to_status=DeviceStatus.IN_REPAIR,
            operator_id=uuid.uuid4(), related_ticket_id=ticket_id,
            repair_vendor="联想售后", repair_cost=500.00, comment="屏幕碎裂",
        )
        assert log["related_ticket_id"] == ticket_id
        assert log["repair_vendor"] == "联想售后"
        assert log["repair_cost"] == 500.00
        assert log["comment"] == "屏幕碎裂"

    def test_log_expected_return_date(self):
        from datetime import date
        return_date = date(2026, 8, 20)
        log = build_device_log(
            device_id=uuid.uuid4(), action=DeviceAction.SEND_REPAIR,
            from_status=DeviceStatus.DAMAGED, to_status=DeviceStatus.IN_REPAIR,
            operator_id=uuid.uuid4(), expected_return_date=return_date,
        )
        assert log["expected_return_date"] == return_date


class TestFullLifecycle:
    """验证完整生命周期路径"""

    def test_normal_flow_to_scrapped(self):
        """正常领用 → 损坏 → 报废"""
        status = get_next_status(DeviceStatus.IN_STOCK, DeviceAction.ALLOCATE)
        assert status == DeviceStatus.ALLOCATED
        status = get_next_status(status, DeviceAction.DELIVER)
        assert status == DeviceStatus.IN_USE
        status = get_next_status(status, DeviceAction.RETURN_DAMAGED)
        assert status == DeviceStatus.DAMAGED
        status = get_next_status(status, DeviceAction.SCRAP)
        assert status == DeviceStatus.SCRAPPED

    def test_repair_flow(self):
        """领用 → 损坏 → 维修 → 修复 → 入库"""
        status = get_next_status(DeviceStatus.IN_STOCK, DeviceAction.ALLOCATE)
        status = get_next_status(status, DeviceAction.DELIVER)
        status = get_next_status(status, DeviceAction.RETURN_DAMAGED)
        status = get_next_status(status, DeviceAction.SEND_REPAIR)
        assert status == DeviceStatus.IN_REPAIR
        status = get_next_status(status, DeviceAction.REPAIR_DONE)
        assert status == DeviceStatus.REPAIRED
        status = get_next_status(status, DeviceAction.RESTOCK)
        assert status == DeviceStatus.IN_STOCK

    def test_direct_scrap_from_in_stock(self):
        """在库设备直接报废"""
        assert get_next_status(DeviceStatus.IN_STOCK, DeviceAction.SCRAP) == DeviceStatus.SCRAPPED

    def test_cancel_allocation(self):
        """分配后取消，回到在库"""
        status = get_next_status(DeviceStatus.IN_STOCK, DeviceAction.ALLOCATE)
        status = get_next_status(status, DeviceAction.CANCEL_ALLOCATE)
        assert status == DeviceStatus.IN_STOCK