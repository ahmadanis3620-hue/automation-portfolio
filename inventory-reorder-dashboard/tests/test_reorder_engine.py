import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reorder_engine import plan_item  # noqa: E402

BASE_ITEM = {
    "sku": "T-1", "name": "Test", "category": "C", "supplier": "S",
    "unit_cost": "10.00", "case_pack": "12", "lead_time_days": "10", "lead_time_std": "0",
    "on_hand": "500", "on_order": "0", "order_cost": "25", "holding_rate": "0.25",
}


def item(**kw):
    return {**BASE_ITEM, **{k: str(v) for k, v in kw.items()}}


class ReorderEngineTest(unittest.TestCase):
    def test_constant_demand_has_zero_safety_stock(self):
        p = plan_item(item(), [10] * 60, 0.95, 7)
        self.assertEqual(p.daily_demand, 10)
        self.assertEqual(p.safety_stock, 0)
        self.assertEqual(p.reorder_point, 100)  # 10/day * 10 days

    def test_lead_time_variability_adds_safety_stock(self):
        p = plan_item(item(lead_time_std=3), [10] * 60, 0.95, 7)
        # z(0.95) * d * sd_L = 1.645 * 10 * 3
        self.assertEqual(p.safety_stock, math.ceil(1.6449 * 30))

    def test_higher_service_level_means_more_safety_stock(self):
        hist = [5, 15] * 30
        low = plan_item(item(), hist, 0.90, 7)
        high = plan_item(item(), hist, 0.99, 7)
        self.assertGreater(high.safety_stock, low.safety_stock)

    def test_statuses(self):
        hist = [10] * 60
        self.assertEqual(plan_item(item(on_hand=0), hist, 0.95, 7).status, "Stockout")
        self.assertEqual(plan_item(item(on_hand=90), hist, 0.95, 7).status, "Reorder now")
        self.assertEqual(plan_item(item(on_hand=150), hist, 0.95, 7).status, "Reorder soon")
        self.assertEqual(plan_item(item(on_hand=500), hist, 0.95, 7).status, "Healthy")
        self.assertEqual(plan_item(item(on_hand=1500), hist, 0.95, 7).status, "Overstock")

    def test_on_order_counts_toward_position(self):
        p = plan_item(item(on_hand=50, on_order=300), [10] * 60, 0.95, 7)
        self.assertEqual(p.position, 350)
        self.assertEqual(p.order_qty, 0)

    def test_order_rounds_up_to_case_pack(self):
        p = plan_item(item(on_hand=20), [10] * 60, 0.95, 7)
        self.assertGreater(p.order_qty, 0)
        self.assertEqual(p.order_qty % 12, 0)
        self.assertGreaterEqual(p.order_qty, p.eoq)

    def test_flags_stockout_before_po_arrives(self):
        self.assertTrue(plan_item(item(on_hand=40), [10] * 60, 0.95, 7).stockout_before_arrival)
        self.assertFalse(plan_item(item(on_hand=400), [10] * 60, 0.95, 7).stockout_before_arrival)


if __name__ == "__main__":
    unittest.main()
