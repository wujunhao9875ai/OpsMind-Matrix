"""仓库种子脚本：初始化库房、设备和库存物品。
首次运行：python -m scripts.seed_warehouse
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import async_session, init_db
from app.models.warehouse_location import WarehouseLocation
from app.models.device import Device
from app.models.inventory import Inventory
from app.core.warehouse_service import _generate_device_no
from sqlalchemy import select


LOCATIONS = [
    {"name": "A栋库房", "code": "WH-A", "address": "A栋1层东侧", "status": "active", "description": "主库房，存放设备和常用耗材"},
    {"name": "B栋库房", "code": "WH-B", "address": "B栋地下1层", "status": "active", "description": "备用库房，存放大型设备"},
    {"name": "维修间", "code": "WH-REPAIR", "address": "C栋2层", "status": "active", "description": "维修周转库房"},
]

DEVICES = [
    {"name": "HP LaserJet Pro M404dn", "model": "M404dn", "category": "printer", "brand": "HP", "status": "in_stock", "purchase_price": 3200.00, "supplier": "京东企业购"},
    {"name": "Canon LBP226dw", "model": "LBP226dw", "category": "printer", "brand": "Canon", "status": "in_stock", "purchase_price": 2800.00, "supplier": "京东企业购"},
    {"name": "Epson L4168 彩色喷墨", "model": "L4168", "category": "printer", "brand": "Epson", "status": "in_use", "purchase_price": 1500.00, "supplier": "天猫企业购"},
    {"name": "Dell OptiPlex 7080 台式机", "model": "OptiPlex 7080", "category": "computer", "brand": "Dell", "status": "in_stock", "purchase_price": 5500.00, "supplier": "Dell直销"},
    {"name": "Lenovo ThinkPad X1 Carbon", "model": "X1 Carbon Gen11", "category": "computer", "brand": "Lenovo", "status": "in_stock", "purchase_price": 9800.00, "supplier": "联想直销"},
    {"name": "MacBook Pro 14", "model": "MacBook Pro 14 M3", "category": "computer", "brand": "Apple", "status": "in_stock", "purchase_price": 14999.00, "supplier": "Apple官网"},
    {"name": "Cisco Catalyst 2960 交换机", "model": "WS-C2960X-24TS-L", "category": "network", "brand": "Cisco", "status": "in_stock", "purchase_price": 4200.00, "supplier": "神州数码"},
    {"name": "H3C SecPath 防火墙", "model": "F1000-AK115", "category": "network", "brand": "H3C", "status": "in_use", "purchase_price": 8500.00, "supplier": "H3C直销"},
    {"name": "Dell 27寸显示器 U2723QE", "model": "U2723QE", "category": "monitor", "brand": "Dell", "status": "in_stock", "purchase_price": 3500.00, "supplier": "Dell直销"},
    {"name": "APC UPS 不间断电源", "model": "BR1500G-CN", "category": "power", "brand": "APC", "status": "in_stock", "purchase_price": 1200.00, "supplier": "京东企业购"},
]

INVENTORIES = [
    {"name": "打印机碳粉 HP 26A", "category": "consumable", "model_spec": "HP 26A", "unit": "个", "quantity": 50, "min_threshold": 10, "max_threshold": 200, "unit_price": 380.00},
    {"name": "打印机硒鼓 Canon 051", "category": "consumable", "model_spec": "Canon 051", "unit": "个", "quantity": 30, "min_threshold": 8, "max_threshold": 150, "unit_price": 450.00},
    {"name": "A4打印纸", "category": "consumable", "model_spec": "70g 500张/包", "unit": "包", "quantity": 200, "min_threshold": 50, "max_threshold": 500, "unit_price": 25.00},
    {"name": "网线 Cat6 3米", "category": "network", "model_spec": "Cat6 3m", "unit": "根", "quantity": 100, "min_threshold": 20, "max_threshold": 300, "unit_price": 15.00},
    {"name": "HDMI线 2米", "category": "cable", "model_spec": "HDMI 2.0 2m", "unit": "根", "quantity": 80, "min_threshold": 15, "max_threshold": 200, "unit_price": 25.00},
    {"name": "USB-C 转接头", "category": "adapter", "model_spec": "USB-C to USB-A/USB-C/HDMI", "unit": "个", "quantity": 60, "min_threshold": 10, "max_threshold": 200, "unit_price": 120.00},
    {"name": "无线鼠标", "category": "peripheral", "model_spec": "Logitech M720", "unit": "个", "quantity": 40, "min_threshold": 10, "max_threshold": 100, "unit_price": 180.00},
    {"name": "键盘套装", "category": "peripheral", "model_spec": "Logitech MK345", "unit": "套", "quantity": 30, "min_threshold": 8, "max_threshold": 80, "unit_price": 150.00},
    {"name": "SSD固态硬盘 512GB", "category": "hardware", "model_spec": "Samsung 870 EVO 512GB", "unit": "个", "quantity": 20, "min_threshold": 5, "max_threshold": 50, "unit_price": 350.00},
    {"name": "DDR4 内存条 16GB", "category": "hardware", "model_spec": "Kingston DDR4 3200MHz 16GB", "unit": "根", "quantity": 15, "min_threshold": 5, "max_threshold": 40, "unit_price": 280.00},
    {"name": "笔记本电源适配器", "category": "power", "model_spec": "65W USB-C", "unit": "个", "quantity": 25, "min_threshold": 5, "max_threshold": 60, "unit_price": 150.00},
    {"name": "墨盒 Epson 003", "category": "consumable", "model_spec": "Epson 003 四色套装", "unit": "套", "quantity": 20, "min_threshold": 5, "max_threshold": 60, "unit_price": 220.00},
]


async def seed():
    await init_db()
    async with async_session() as db:
        location_ids = {}
        # 创建库房
        for loc_data in LOCATIONS:
            result = await db.execute(select(WarehouseLocation).where(WarehouseLocation.code == loc_data["code"]))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"跳过已存在的库房: {loc_data['name']} ({loc_data['code']})")
                location_ids[loc_data["code"]] = existing.id
                continue
            loc = WarehouseLocation(**loc_data)
            db.add(loc)
            await db.flush()
            location_ids[loc_data["code"]] = loc.id
            print(f"创建库房: {loc_data['name']} ({loc_data['code']})")

        # 创建设备
        for dev_data in DEVICES:
            device_no = _generate_device_no(dev_data["category"])
            result = await db.execute(select(Device).where(Device.device_no == device_no))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"跳过已存在的设备: {dev_data['name']} ({device_no})")
                continue

            location_code = "WH-A" if dev_data["status"] == "in_stock" else "WH-B"
            device = Device(
                device_no=device_no,
                location_id=location_ids.get(location_code),
                **dev_data,
            )
            db.add(device)
            print(f"创建设备: {dev_data['name']} ({device_no})")

        # 创建库存物品
        for inv_data in INVENTORIES:
            result = await db.execute(select(Inventory).where(Inventory.name == inv_data["name"]))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"跳过已存在的库存物品: {inv_data['name']}")
                continue
            inv = Inventory(
                available_quantity=inv_data["quantity"],
                location_id=location_ids["WH-A"],
                **inv_data,
            )
            db.add(inv)
            print(f"创建库存物品: {inv_data['name']} ({inv_data['quantity']}{inv_data['unit']})")

        await db.commit()
    print("\n仓库种子数据初始化完成！")


if __name__ == "__main__":
    asyncio.run(seed())