"""Reconcile core project outputs and fail fast when results drift."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "ecommerce.db"
SUMMARY_PATH = ROOT / "outputs" / "summary_metrics.json"


def scalar(conn: sqlite3.Connection, query: str):
    return conn.execute(query).fetchone()[0]


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    with sqlite3.connect(DB_PATH) as conn:
        checks = {
            "raw line count": scalar(conn, "SELECT COUNT(*) FROM transaction_lines") == 541_909,
            "valid line count": scalar(conn, "SELECT SUM(is_valid_sale) FROM transaction_lines") == 397_884,
            "order count": scalar(conn, "SELECT COUNT(*) FROM orders") == summary["orders"],
            "customer count": scalar(conn, "SELECT COUNT(*) FROM customers") == summary["customers"],
            "unique order IDs": scalar(conn, "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM orders") == 0,
            "order/item revenue reconciliation": abs(
                scalar(conn, "SELECT SUM(order_revenue) FROM orders")
                - scalar(conn, "SELECT SUM(line_revenue) FROM order_items")
            ) < 0.01,
            "summary revenue reconciliation": abs(
                scalar(conn, "SELECT SUM(order_revenue) FROM orders") - summary["revenue"]
            ) < 0.01,
            "positive valid quantities": scalar(conn, "SELECT MIN(quantity) FROM order_items") > 0,
            "positive valid prices": scalar(conn, "SELECT MIN(unit_price) FROM order_items") > 0,
        }

    expected_outputs = [
        ROOT / "outputs" / "figures" / "executive_dashboard.png",
        ROOT / "outputs" / "figures" / "monthly_revenue.png",
        ROOT / "outputs" / "figures" / "cohort_retention.png",
        ROOT / "outputs" / "tables" / "rfm_segments.csv",
        ROOT / "outputs" / "tables" / "cohort_retention.csv",
        ROOT / "notebooks" / "ecommerce_analysis.ipynb",
    ]
    checks["expected outputs exist"] = all(path.exists() and path.stat().st_size > 0 for path in expected_outputs)

    status = pd.DataFrame(checks.items(), columns=["check", "passed"])
    print(status.to_string(index=False))
    if not status["passed"].all():
        failed = status.loc[~status["passed"], "check"].tolist()
        raise SystemExit(f"Validation failed: {failed}")
    print("\nAll project validations passed.")


if __name__ == "__main__":
    main()

