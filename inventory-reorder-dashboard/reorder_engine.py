"""Inventory reorder engine: safety stock, reorder points, EOQ and purchase orders.

Pure Python standard library, so it runs anywhere (a cron job, a cloud function,
a Google Sheets webhook) with no installs.

Usage:
    python reorder_engine.py                      # defaults: 95% service level, 7-day review
    python reorder_engine.py --service-level 0.98 --review-days 14

Reads:  data/items.csv, data/sales_history.csv
Writes: output/reorder_plan.csv       one row per SKU with every metric
        output/purchase_orders.csv    suggested PO lines grouped by supplier
        data.js                       raw data for the browser dashboard
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist, mean, pstdev

HERE = Path(__file__).parent
FORECAST_WINDOW = 56      # days of recent history used for the demand rate
WATCH_DAYS = 7            # "reorder soon" if within a week of the reorder point
OVERSTOCK_DAYS = 120      # more than ~4 months of cover ties up cash


@dataclass
class Plan:
    sku: str
    name: str
    category: str
    supplier: str
    unit_cost: float
    on_hand: int
    on_order: int
    position: int
    daily_demand: float
    demand_std: float
    lead_time_days: float
    safety_stock: int
    reorder_point: int
    eoq: int
    days_of_cover: float
    status: str
    order_qty: int
    order_value: float
    stockout_before_arrival: bool


def z_for(service_level: float) -> float:
    return NormalDist().inv_cdf(service_level)


def plan_item(item: dict, history: list[int], service_level: float, review_days: int) -> Plan:
    recent = history[-FORECAST_WINDOW:]
    d = mean(recent)
    sd = pstdev(recent)
    lt = float(item["lead_time_days"])
    lt_sd = float(item["lead_time_std"])
    cost = float(item["unit_cost"])
    pack = int(item["case_pack"])
    on_hand = int(item["on_hand"])
    on_order = int(item["on_order"])
    position = on_hand + on_order

    # Safety stock covering both demand variability and supplier lead-time variability
    safety = z_for(service_level) * math.sqrt(lt * sd**2 + (d**2) * lt_sd**2)
    rop = d * lt + safety

    annual_demand = d * 365
    holding_cost = cost * float(item["holding_rate"])
    eoq = math.sqrt(2 * annual_demand * float(item["order_cost"]) / holding_cost) if d > 0 else 0

    days_cover = on_hand / d if d > 0 else math.inf

    if on_hand == 0:
        status = "Stockout"
    elif position <= rop:
        status = "Reorder now"
    elif position <= rop + d * WATCH_DAYS:
        status = "Reorder soon"
    elif days_cover > OVERSTOCK_DAYS:
        status = "Overstock"
    else:
        status = "Healthy"

    qty = 0
    if status in ("Stockout", "Reorder now"):
        order_up_to = rop + d * review_days
        qty = max(order_up_to - position, eoq)
        qty = math.ceil(qty / pack) * pack  # suppliers ship whole cases

    return Plan(
        sku=item["sku"], name=item["name"], category=item["category"], supplier=item["supplier"],
        unit_cost=cost, on_hand=on_hand, on_order=on_order, position=position,
        daily_demand=round(d, 2), demand_std=round(sd, 2), lead_time_days=lt,
        safety_stock=math.ceil(safety), reorder_point=math.ceil(rop), eoq=math.ceil(eoq),
        days_of_cover=round(days_cover, 1), status=status,
        order_qty=qty, order_value=round(qty * cost, 2),
        stockout_before_arrival=on_hand < d * lt,
    )


def load(data_dir: Path) -> tuple[list[dict], dict[str, list[int]], list[str]]:
    with open(data_dir / "items.csv", newline="") as f:
        items = list(csv.DictReader(f))
    history: dict[str, list[int]] = defaultdict(list)
    dates: list[str] = []
    with open(data_dir / "sales_history.csv", newline="") as f:
        for row in csv.DictReader(f):  # rows are date-ordered per SKU
            history[row["sku"]].append(int(row["units"]))
            if row["sku"] == items[0]["sku"]:
                dates.append(row["date"])
    return items, history, dates


def run(service_level: float = 0.95, review_days: int = 7, base: Path = HERE) -> list[Plan]:
    items, history, dates = load(base / "data")
    plans = [plan_item(it, history[it["sku"]], service_level, review_days) for it in items]

    out = base / "output"
    out.mkdir(exist_ok=True)
    with open(out / "reorder_plan.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(plans[0])))
        w.writeheader()
        w.writerows(asdict(p) for p in plans)
    with open(out / "purchase_orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["supplier", "sku", "name", "order_qty", "unit_cost", "line_value"])
        for p in sorted(plans, key=lambda p: (p.supplier, p.sku)):
            if p.order_qty:
                w.writerow([p.supplier, p.sku, p.name, p.order_qty, f"{p.unit_cost:.2f}", f"{p.order_value:.2f}"])

    payload = {
        "dates": dates,
        "items": [{**it, "history": history[it["sku"]]} for it in items],
        "params": {"forecastWindow": FORECAST_WINDOW, "watchDays": WATCH_DAYS, "overstockDays": OVERSTOCK_DAYS},
    }
    (base / "data.js").write_text("window.REORDER_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    return plans


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--service-level", type=float, default=0.95)
    ap.add_argument("--review-days", type=int, default=7)
    args = ap.parse_args()
    plans = run(args.service_level, args.review_days)

    counts: dict[str, int] = defaultdict(int)
    for p in plans:
        counts[p.status] += 1
    to_order = [p for p in plans if p.order_qty]
    print(f"Planned {len(plans)} SKUs at {args.service_level:.0%} service level")
    for s in ("Stockout", "Reorder now", "Reorder soon", "Healthy", "Overstock"):
        print(f"  {s:<13} {counts[s]}")
    print(f"Suggested POs: {len(to_order)} lines, ${sum(p.order_value for p in to_order):,.2f}")
    print("Wrote output/reorder_plan.csv, output/purchase_orders.csv, data.js")


if __name__ == "__main__":
    main()
