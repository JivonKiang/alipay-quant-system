"""
Tests for Fee Manager
TDD: RED-GREEN-REFACTOR
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from risk.fee_manager import FeeManager


def test_default_lock_7_days():
    """测试默认7天锁定"""
    fm = FeeManager({"default_lock_days": 7, "fee_schedule": [
        {"max_days": 6, "rate": 0.015, "label": "1.5%", "severity": "BLOCK"},
        {"max_days": 29, "rate": 0.005, "label": "0.5%", "severity": "WARN"},
        {"max_days": 9999, "rate": 0.0, "label": "0%", "severity": "OK"},
    ]})

    # 持有3天 → BLOCK
    tier = fm.get_fee_tier(3, "005844")
    assert tier["severity"] == "BLOCK"
    assert tier["fee_rate"] == 0.015

    # 持有15天 → WARN
    tier = fm.get_fee_tier(15, "005844")
    assert tier["severity"] == "WARN"
    assert tier["fee_rate"] == 0.005

    # 持有35天 → OK
    tier = fm.get_fee_tier(35, "005844")
    assert tier["severity"] == "OK"
    assert tier["fee_rate"] == 0.0

    print("✅ test_default_lock_7_days PASSED")


def test_custom_lock_30_days():
    """测试自定义30天锁定"""
    fm = FeeManager({
        "default_lock_days": 7,
        "custom_lock_days": {"TEST001": 30},
        "fee_schedule": [
            {"max_days": 6, "rate": 0.015, "label": "1.5%", "severity": "BLOCK"},
            {"max_days": 29, "rate": 0.005, "label": "0.5%", "severity": "WARN"},
            {"max_days": 9999, "rate": 0.0, "label": "0%", "severity": "OK"},
        ]
    })

    # 自定义基金 持有15天 → 仍在BLOCK (锁定30天)
    tier = fm.get_fee_tier(15, "TEST001")
    assert tier["severity"] == "BLOCK", f"Expected BLOCK, got {tier['severity']}"

    # 持有35天 → OK (已超过30天锁定)
    tier = fm.get_fee_tier(35, "TEST001")
    assert tier["severity"] == "OK"

    print("✅ test_custom_lock_30_days PASSED")


def test_net_return_calculation():
    """测试净收益计算"""
    fm = FeeManager({"default_lock_days": 7, "fee_schedule": [
        {"max_days": 6, "rate": 0.015, "label": "1.5%", "severity": "BLOCK"},
        {"max_days": 29, "rate": 0.005, "label": "0.5%", "severity": "WARN"},
        {"max_days": 9999, "rate": 0.0, "label": "0%", "severity": "OK"},
    ]})

    # 盈利12%, 持有15天(0.5%费率) → 净赚11.5%
    net = fm.calculate_net_return(12.0, 15, "005844")
    assert abs(net - 11.5) < 0.001

    # 盈利12%, 持有35天(0%费率) → 净赚12%
    net = fm.calculate_net_return(12.0, 35, "005844")
    assert abs(net - 12.0) < 0.001

    print("✅ test_net_return_calculation PASSED")


def test_can_redeem():
    """测试赎回权限判断"""
    fm = FeeManager({"default_lock_days": 7, "fee_schedule": [
        {"max_days": 6, "rate": 0.015, "label": "1.5%", "severity": "BLOCK"},
        {"max_days": 29, "rate": 0.005, "label": "0.5%", "severity": "WARN"},
        {"max_days": 9999, "rate": 0.0, "label": "0%", "severity": "OK"},
    ]})

    assert fm.can_redeem(3) == False   # BLOCK
    assert fm.can_redeem(15) == True   # WARN
    assert fm.can_redeem(35) == True   # OK

    print("✅ test_can_redeem PASSED")


if __name__ == "__main__":
    test_default_lock_7_days()
    test_custom_lock_30_days()
    test_net_return_calculation()
    test_can_redeem()
    print("\n🎉 All fee_manager tests passed!")
