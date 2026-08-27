import pytest


@pytest.fixture
def sample_device_data():
    return {
        "name": "HP LaserJet Pro",
        "model": "M404dn",
        "category": "printer",
        "brand": "HP",
        "serial_number": "SN12345678",
    }


@pytest.fixture
def sample_inventory_data():
    return {
        "name": "打印机碳粉",
        "category": "consumable",
        "model_spec": "HP 26A",
        "unit": "个",
        "quantity": 50,
        "min_threshold": 10,
        "max_threshold": 200,
    }


@pytest.fixture
def sample_location_data():
    return {
        "name": "A栋库房",
        "code": "WH-A",
        "address": "A栋1层",
    }