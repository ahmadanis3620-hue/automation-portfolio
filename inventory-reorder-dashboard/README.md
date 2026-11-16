# Inventory Reorder Dashboard

**Live demo:** https://ahmadanis3620-hue.github.io/automation-portfolio/inventory-reorder-dashboard/

Turns raw sales history into **reorder points, safety stock and ready-to-send purchase orders**, so a small e-commerce team stops guessing when to reorder and stops tying up cash in overstock.

The store, products and suppliers are fictional sample data: "Trailhead Home & Outdoor", 36 SKUs, 4 suppliers, 180 days of sales.

## What it does

- Flags every SKU as **Stockout**, **Reorder now**, **Reorder soon**, **Healthy** or **Overstock**.
- Warns when a product **will run out before a new PO can arrive**.
- Calculates safety stock that covers both demand swings and late suppliers.
- Suggests order quantities using EOQ, rounded up to whole supplier cases.
- Groups suggested orders by supplier and **exports POs to CSV**.
- Lets you change the service level (90–99%) and review cycle, and recalculates everything.
- Shows a 90-day demand chart and a 60-day on-hand projection for each SKU.

## The math

| Metric | Formula |
|---|---|
| Demand rate `d`, variability `σd` | Mean and std. dev. of the last 56 days of sales |
| Safety stock | `z × √(L·σd² + d²·σL²)` (demand + lead-time variability) |
| Reorder point | `d × L + safety stock` |
| EOQ | `√(2 × annual demand × order cost / holding cost)` |
| Order qty | `max(EOQ, ROP + d × review cycle − position)`, rounded up to the case pack |

The inventory position includes stock already on order.

## Run it yourself

Only the Python standard library is needed (3.8+).

```bash
python generate_sample_data.py              # rebuild data/*.csv (optional)
python reorder_engine.py                    # 95% service level, weekly review
python reorder_engine.py --service-level 0.98 --review-days 14
python -m unittest discover -s tests        # 7 tests
```

Outputs:
- `output/reorder_plan.csv`: every metric for every SKU
- `output/purchase_orders.csv`: PO lines grouped by supplier
- `data.js`: the data the dashboard reads

Then open `index.html` in a browser. It is one self-contained file with no build step.

## Using it with real data

Swap the two CSVs for an export from Shopify, Amazon Seller Central, an ERP or a Google Sheet:

- `items.csv`: sku, name, category, supplier, unit_cost, case_pack, lead_time_days, lead_time_std, on_hand, on_order, order_cost, holding_rate
- `sales_history.csv`: date, sku, units

In a client project this runs on a schedule (cron, GitHub Actions or a cloud function), pulls data straight from the store's API, and emails or Slacks the POs every morning.
