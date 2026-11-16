"""Generate a realistic, fictional sample dataset for the reorder demo.

The store ("Trailhead Home & Outdoor") and its suppliers are made up.
Demand has weekly seasonality, trends, promotions and some intermittent SKUs,
so the reorder math has something real to chew on.

Usage:  python generate_sample_data.py
Writes: data/items.csv, data/sales_history.csv
"""
from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
SEED = 42
DAYS = 180
END_DATE = date(2026, 11, 15)

SUPPLIERS = {
    "Pinecrest Supply": (7, 1.5),      # (mean lead time days, std dev)
    "Harbor Goods Co.": (14, 3.0),
    "Summit Imports": (35, 7.0),
    "Lakeview Mfg": (10, 2.0),
}

# name, category, supplier, unit_cost, case_pack, base daily demand, trend/day, pattern
CATALOG = [
    ("Insulated Water Bottle 32oz", "Hydration", "Summit Imports", 6.40, 24, 18, 0.02, "steady"),
    ("Insulated Water Bottle 20oz", "Hydration", "Summit Imports", 5.10, 24, 11, 0.00, "steady"),
    ("Collapsible Silicone Cup", "Hydration", "Summit Imports", 2.20, 48, 6, -0.01, "steady"),
    ("Water Filter Straw", "Hydration", "Harbor Goods Co.", 4.75, 36, 9, 0.03, "promo"),
    ("Camp Mug Enamel", "Kitchen", "Lakeview Mfg", 3.90, 24, 7, 0.00, "steady"),
    ("Pour-Over Coffee Kit", "Kitchen", "Lakeview Mfg", 11.50, 12, 4, 0.02, "steady"),
    ("Cast Iron Skillet 10in", "Kitchen", "Lakeview Mfg", 14.20, 6, 5, 0.00, "steady"),
    ("Cutlery Set Titanium", "Kitchen", "Summit Imports", 8.30, 20, 3, 0.00, "intermittent"),
    ("Compact Stove Burner", "Kitchen", "Summit Imports", 19.80, 10, 2, 0.01, "intermittent"),
    ("Fuel Canister 230g", "Kitchen", "Pinecrest Supply", 3.10, 24, 14, 0.00, "weekend"),
    ("LED Headlamp 400lm", "Lighting", "Summit Imports", 9.60, 20, 12, 0.04, "steady"),
    ("Rechargeable Lantern", "Lighting", "Summit Imports", 15.40, 12, 6, 0.03, "steady"),
    ("String Lights Solar 20ft", "Lighting", "Harbor Goods Co.", 7.80, 24, 8, 0.05, "promo"),
    ("AA Lithium Batteries 8pk", "Lighting", "Pinecrest Supply", 6.90, 24, 16, 0.00, "steady"),
    ("Ultralight Tent 2P", "Shelter", "Summit Imports", 88.00, 4, 2, 0.00, "weekend"),
    ("Tent Footprint 2P", "Shelter", "Summit Imports", 14.00, 10, 1.5, 0.00, "intermittent"),
    ("Hammock Double", "Shelter", "Harbor Goods Co.", 17.50, 10, 5, -0.01, "weekend"),
    ("Tarp 10x10 Ripstop", "Shelter", "Harbor Goods Co.", 12.30, 12, 3, 0.00, "steady"),
    ("Sleeping Bag 30F", "Sleep", "Summit Imports", 42.00, 4, 3, 0.02, "steady"),
    ("Inflatable Sleeping Pad", "Sleep", "Summit Imports", 24.50, 8, 4, 0.01, "steady"),
    ("Camp Pillow", "Sleep", "Harbor Goods Co.", 6.20, 24, 6, 0.00, "steady"),
    ("Fleece Blanket Throw", "Sleep", "Lakeview Mfg", 9.40, 12, 7, 0.06, "promo"),
    ("Daypack 22L", "Packs", "Summit Imports", 21.00, 8, 5, 0.00, "steady"),
    ("Hydration Pack 2L", "Packs", "Summit Imports", 18.60, 8, 3, -0.01, "steady"),
    ("Dry Bag 10L", "Packs", "Harbor Goods Co.", 5.30, 30, 9, 0.00, "weekend"),
    ("Packing Cubes Set", "Packs", "Harbor Goods Co.", 8.10, 20, 8, 0.02, "steady"),
    ("First Aid Kit Trail", "Safety", "Pinecrest Supply", 11.20, 12, 6, 0.00, "steady"),
    ("Emergency Bivy", "Safety", "Pinecrest Supply", 4.40, 40, 5, 0.00, "steady"),
    ("Bear Spray 7.9oz", "Safety", "Pinecrest Supply", 22.00, 12, 3, -0.02, "steady"),
    ("Whistle & Compass Combo", "Safety", "Pinecrest Supply", 2.10, 50, 4, 0.00, "intermittent"),
    ("Trekking Poles Pair", "Trail", "Summit Imports", 16.80, 10, 4, 0.01, "weekend"),
    ("Microspikes Traction", "Trail", "Summit Imports", 13.50, 12, 2, 0.08, "steady"),
    ("Merino Hiking Socks", "Trail", "Lakeview Mfg", 5.60, 36, 20, 0.03, "steady"),
    ("Gaiters Waterproof", "Trail", "Lakeview Mfg", 9.90, 12, 1, 0.00, "intermittent"),
    ("Sunscreen Stick SPF50", "Trail", "Pinecrest Supply", 2.80, 48, 10, -0.04, "steady"),
    ("Bug Repellent Spray", "Trail", "Pinecrest Supply", 3.30, 48, 8, -0.04, "steady"),
]

# Hand-picked starting positions so the demo shows every status.
# (on_hand multiplier of mean daily demand, on_order multiplier)
STOCK_SCENARIOS = {
    0: (6, 0), 3: (0, 0), 10: (9, 0), 12: (4, 30), 14: (40, 0), 21: (18, 0),
    22: (160, 0), 25: (3, 0), 28: (190, 0), 31: (0, 20), 32: (11, 0), 34: (210, 0),
}


def daily_units(rng: random.Random, base: float, trend: float, pattern: str, t: int, d: date) -> int:
    level = max(0.3, base * (1 + trend * (t - DAYS) / 30))
    weekday = d.weekday()
    if pattern == "weekend":
        level *= 1.6 if weekday >= 4 else 0.75
    else:
        level *= 1.15 if weekday >= 4 else 0.95
    if pattern == "promo" and (t % 45) in range(0, 5):
        level *= 2.2
    if pattern == "intermittent":
        return 0 if rng.random() < 0.55 else max(0, round(rng.gauss(level * 2.2, level)))
    # Poisson-ish noise
    return max(0, round(rng.gauss(level, math.sqrt(level) * 1.1)))


def main() -> None:
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    start = END_DATE - timedelta(days=DAYS - 1)

    items, sales = [], []
    for i, (name, cat, sup, cost, pack, base, trend, pattern) in enumerate(CATALOG):
        sku = f"TH-{1001 + i}"
        lt, lt_sd = SUPPLIERS[sup]
        history = []
        for t in range(DAYS):
            d = start + timedelta(days=t)
            units = daily_units(rng, base, trend, pattern, t, d)
            history.append(units)
            sales.append({"date": d.isoformat(), "sku": sku, "units": units})
        recent = sum(history[-56:]) / 56
        oh_mult, oo_mult = STOCK_SCENARIOS.get(i, (rng.uniform(lt + 12, lt + 45), 0))
        items.append({
            "sku": sku, "name": name, "category": cat, "supplier": sup,
            "unit_cost": f"{cost:.2f}", "case_pack": pack,
            "lead_time_days": lt, "lead_time_std": lt_sd,
            "on_hand": round(recent * oh_mult), "on_order": round(recent * oo_mult),
            "order_cost": 45 if sup == "Summit Imports" else 25,
            "holding_rate": 0.25,
        })

    with open(DATA / "items.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0]))
        w.writeheader()
        w.writerows(items)
    with open(DATA / "sales_history.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "sku", "units"])
        w.writeheader()
        w.writerows(sales)
    print(f"Wrote {len(items)} items and {len(sales):,} sales rows to {DATA}")


if __name__ == "__main__":
    main()
