"""库存守卫单元测试：阈值检查、异常类"""
import pytest
from datetime import datetime, timezone, timedelta
from app.core.inventory_guard import (
    check_low_stock, check_out_of_stock, check_idle,
    InventoryConcurrentError, InventoryInsufficientError,
)


class FakeInventory:
    """模拟 Inventory 对象，避免数据库依赖"""
    def __init__(self, name="test", quantity=0, available_quantity=0,
                 min_threshold=5, max_threshold=100, last_restock_at=None):
        self.name = name
        self.quantity = quantity
        self.available_quantity = available_quantity
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.last_restock_at = last_restock_at


class TestCheckLowStock:
    """低库存检查"""

    def test_below_threshold(self):
        inv = FakeInventory(quantity=3, min_threshold=5)
        assert check_low_stock(inv) is True

    def test_equal_to_threshold(self):
        inv = FakeInventory(quantity=5, min_threshold=5)
        assert check_low_stock(inv) is True

    def test_above_threshold(self):
        inv = FakeInventory(quantity=10, min_threshold=5)
        assert check_low_stock(inv) is False

    def test_zero_quantity(self):
        inv = FakeInventory(quantity=0, min_threshold=5)
        assert check_low_stock(inv) is True


class TestCheckOutOfStock:
    """库存耗尽检查"""

    def test_out_of_stock(self):
        inv = FakeInventory(quantity=0)
        assert check_out_of_stock(inv) is True

    def test_has_stock(self):
        inv = FakeInventory(quantity=1)
        assert check_out_of_stock(inv) is False

    def test_negative_not_considered(self):
        """负库存不应出现，但仍按 != 0 处理"""
        inv = FakeInventory(quantity=-1)
        assert check_out_of_stock(inv) is False


class TestCheckIdle:
    """呆滞库存检查"""

    def test_recently_restocked(self):
        inv = FakeInventory(
            last_restock_at=datetime.now(timezone.utc) - timedelta(days=30)
        )
        assert check_idle(inv, days=180) is False

    def test_idle_for_long_time(self):
        inv = FakeInventory(
            last_restock_at=datetime.now(timezone.utc) - timedelta(days=200)
        )
        assert check_idle(inv, days=180) is True

    def test_never_restocked(self):
        inv = FakeInventory(last_restock_at=None)
        assert check_idle(inv) is False

    def test_custom_days_threshold(self):
        inv = FakeInventory(
            last_restock_at=datetime.now(timezone.utc) - timedelta(days=60)
        )
        assert check_idle(inv, days=30) is True
        assert check_idle(inv, days=90) is False


class TestCustomExceptions:
    """异常类测试"""

    def test_inventory_concurrent_error(self):
        err = InventoryConcurrentError("入库并发冲突")
        assert str(err) == "入库并发冲突"
        assert isinstance(err, Exception)

    def test_inventory_insufficient_error(self):
        err = InventoryInsufficientError("库存不足: 碳粉 可用 3，需要 5")
        assert "库存不足" in str(err)
        assert isinstance(err, Exception)