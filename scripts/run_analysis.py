"""Run the SQL analysis, export result tables, and create portfolio visuals."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "ecommerce.db"
SQL_PATH = ROOT / "sql" / "analysis.sql"
TABLE_DIR = ROOT / "outputs" / "tables"
FIGURE_DIR = ROOT / "outputs" / "figures"

NAVY = "#0F172A"
TEAL = "#0F766E"
MINT = "#14B8A6"
SLATE = "#64748B"
LIGHT = "#E2E8F0"
AMBER = "#D97706"
RED = "#DC2626"


def load_queries() -> dict[str, str]:
    text = SQL_PATH.read_text(encoding="utf-8")
    parts = re.split(r"^-- query: ([a-z0-9_]+)\s*$", text, flags=re.MULTILINE)
    return {
        parts[index]: parts[index + 1].strip()
        for index in range(1, len(parts), 2)
        if parts[index + 1].strip()
    }


def run_queries() -> dict[str, pd.DataFrame]:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, pd.DataFrame] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for name, query in load_queries().items():
            frame = pd.read_sql_query(query, conn)
            frame.to_csv(TABLE_DIR / f"{name}.csv", index=False)
            results[name] = frame
            print(f"{name}: {len(frame):,} rows")
    return results


def set_plot_style() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": LIGHT,
            "axes.labelcolor": NAVY,
            "axes.titlecolor": NAVY,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "xtick.color": SLATE,
            "ytick.color": SLATE,
            "grid.color": LIGHT,
            "grid.alpha": 0.7,
        }
    )


def save_figure(fig: plt.Figure, filename: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / filename, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_monthly_revenue(monthly: pd.DataFrame) -> None:
    plot_data = monthly.copy()
    plot_data["month"] = pd.to_datetime(plot_data["order_month"])
    plot_data["revenue_thousands"] = plot_data["revenue"] / 1_000
    complete = plot_data[plot_data["is_partial_month"] == 0]
    partial = plot_data[plot_data["is_partial_month"] == 1]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(plot_data["month"], plot_data["revenue_thousands"], color=TEAL, linewidth=2.6)
    ax.fill_between(plot_data["month"], plot_data["revenue_thousands"], color=MINT, alpha=0.12)
    ax.scatter(complete["month"], complete["revenue_thousands"], color=TEAL, s=48, zorder=3)
    ax.scatter(
        partial["month"], partial["revenue_thousands"], facecolor="white",
        edgecolor=AMBER, linewidth=2, s=70, zorder=4, label="Partial month",
    )
    peak = complete.loc[complete["revenue"].idxmax()]
    ax.annotate(
        f"Peak complete month\n£{peak['revenue'] / 1_000:,.0f}K",
        (peak["month"], peak["revenue_thousands"]), xytext=(12, -44),
        textcoords="offset points", color=NAVY,
        arrowprops={"arrowstyle": "-", "color": SLATE},
    )
    ax.set_title("Monthly revenue accelerated into the holiday season", loc="left", pad=14)
    ax.set_ylabel("Revenue (£ thousands)")
    ax.set_xlabel("")
    ax.legend(frameon=False, loc="upper left")
    sns.despine(ax=ax)
    save_figure(fig, "monthly_revenue.png")


def plot_segments(segments: pd.DataFrame) -> None:
    plot_data = segments.sort_values("revenue", ascending=True).copy()
    plot_data["revenue_millions"] = plot_data["revenue"] / 1_000_000
    colors = [RED if value == "At Risk" else TEAL for value in plot_data["segment"]]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.barh(plot_data["segment"], plot_data["revenue_millions"], color=colors)
    ax.bar_label(bars, labels=[f"£{value:.2f}M" for value in plot_data["revenue_millions"]], padding=6)
    ax.set_title("RFM segments show where retention effort can protect revenue", loc="left", pad=14)
    ax.set_xlabel("Historical revenue (£ millions)")
    ax.set_ylabel("")
    ax.grid(axis="y", visible=False)
    sns.despine(ax=ax, left=True)
    save_figure(fig, "rfm_segments.png")


def plot_cohort_retention(cohort: pd.DataFrame) -> None:
    matrix = cohort.pivot(index="cohort_month", columns="month_number", values="retention_rate_pct")
    matrix.index = pd.to_datetime(matrix.index).strftime("%b %Y")
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.heatmap(
        matrix, cmap=sns.light_palette(TEAL, as_cmap=True), vmin=0, vmax=100,
        linewidths=0.5, linecolor="white", annot=True, fmt=".0f",
        cbar_kws={"label": "Retention rate (%)"}, ax=ax,
    )
    ax.set_title("Monthly cohort retention falls sharply after the first purchase", loc="left", pad=14)
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("First purchase cohort")
    save_figure(fig, "cohort_retention.png")


def plot_revenue_concentration(concentration: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = concentration["revenue_decile"]
    ax.bar(x, concentration["revenue_share_pct"], color=MINT, alpha=0.85, label="Decile share")
    ax.plot(
        x, concentration["cumulative_revenue_share_pct"], color=NAVY,
        marker="o", linewidth=2.4, label="Cumulative share",
    )
    ax.axhline(80, color=AMBER, linewidth=1.3, linestyle="--", alpha=0.8)
    ax.set_title("A small customer group accounts for most revenue", loc="left", pad=14)
    ax.set_xlabel("Customer revenue decile (1 = highest value)")
    ax.set_ylabel("Revenue share (%)")
    ax.set_xticks(range(1, 11))
    ax.set_ylim(0, 105)
    ax.legend(frameon=False)
    sns.despine(ax=ax)
    save_figure(fig, "revenue_concentration.png")


def plot_top_products(products: pd.DataFrame) -> None:
    plot_data = products.nsmallest(10, "revenue_rank").sort_values("revenue")
    labels = plot_data["description"].str.title().str.slice(0, 38)
    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(labels, plot_data["revenue"] / 1_000, color=TEAL)
    ax.bar_label(bars, labels=[f"£{value / 1_000:.0f}K" for value in plot_data["revenue"]], padding=5)
    ax.set_title("Top products by valid sales revenue", loc="left", pad=14)
    ax.set_xlabel("Revenue (£ thousands)")
    ax.set_ylabel("")
    ax.grid(axis="y", visible=False)
    sns.despine(ax=ax, left=True)
    save_figure(fig, "top_products.png")


def build_summary(results: dict[str, pd.DataFrame]) -> dict[str, object]:
    kpi = results["kpi_summary"].iloc[0]
    monthly = results["monthly_revenue"]
    complete_months = monthly[monthly["is_partial_month"] == 0]
    peak = complete_months.loc[complete_months["revenue"].idxmax()]
    frequency = results["customer_purchase_frequency"]
    one_order = frequency.loc[frequency["purchase_frequency"] == "1 order"].iloc[0]
    repeat_timing = results["reorder_timing"]
    concentration = results["revenue_concentration"]
    segments = results["rfm_segments"]
    at_risk = segments.loc[segments["segment"] == "At Risk"].iloc[0]
    countries = results["country_performance"]
    non_uk = countries[countries["country"] != "United Kingdom"].iloc[0]
    product = results["top_products"].iloc[0]

    return {
        "revenue": round(float(kpi["revenue"]), 2),
        "orders": int(kpi["orders"]),
        "customers": int(kpi["customers"]),
        "average_order_value": round(float(kpi["average_order_value"]), 2),
        "repeat_customer_rate_pct": round(float(kpi["repeat_customer_rate_pct"]), 2),
        "cancelled_value": round(float(kpi["cancelled_value"]), 2),
        "peak_complete_month": str(peak["order_month"]),
        "peak_complete_month_revenue": round(float(peak["revenue"]), 2),
        "one_order_customers": int(one_order["customers"]),
        "one_order_customer_pct": round(100 * float(one_order["customers"]) / float(kpi["customers"]), 2),
        "median_days_to_second_order": int(repeat_timing["days_to_second_order"].median()),
        "top_decile_revenue_share_pct": round(float(concentration.iloc[0]["revenue_share_pct"]), 2),
        "top_three_deciles_cumulative_share_pct": round(float(concentration.iloc[2]["cumulative_revenue_share_pct"]), 2),
        "at_risk_customers": int(at_risk["customers"]),
        "at_risk_historical_revenue": round(float(at_risk["revenue"]), 2),
        "top_non_uk_market": str(non_uk["country"]),
        "top_non_uk_market_revenue": round(float(non_uk["revenue"]), 2),
        "top_product": str(product["description"]).title(),
        "top_product_revenue": round(float(product["revenue"]), 2),
    }


def create_executive_dashboard(results: dict[str, pd.DataFrame], summary: dict[str, object]) -> None:
    monthly = results["monthly_revenue"].copy()
    monthly["month"] = pd.to_datetime(monthly["order_month"])
    segments = results["rfm_segments"].sort_values("revenue", ascending=True)
    concentration = results["revenue_concentration"]

    fig = plt.figure(figsize=(16, 10), facecolor="white")
    grid = fig.add_gridspec(3, 12, height_ratios=[1.1, 3.6, 3.6], hspace=0.65, wspace=1.1)
    fig.suptitle(
        "E-Commerce Customer & Revenue Analysis", x=0.05, y=0.98, ha="left",
        fontsize=24, fontweight="bold", color=NAVY,
    )
    fig.text(
        0.05, 0.943, "UCI Online Retail. Valid customer-linked sales, Dec 2010–Dec 2011.",
        color=SLATE, fontsize=11,
    )

    cards = [
        ("Revenue", f"£{summary['revenue'] / 1_000_000:.2f}M"),
        ("Orders", f"{summary['orders']:,}"),
        ("Customers", f"{summary['customers']:,}"),
        ("Repeat customers", f"{summary['repeat_customer_rate_pct']:.1f}%"),
    ]
    for index, (label, value) in enumerate(cards):
        ax = fig.add_subplot(grid[0, index * 3 : (index + 1) * 3])
        ax.set_facecolor("#F8FAFC")
        for spine in ax.spines.values():
            spine.set_color(LIGHT)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.06, 0.68, label, transform=ax.transAxes, color=SLATE, fontsize=10)
        ax.text(0.06, 0.22, value, transform=ax.transAxes, color=NAVY, fontsize=22, fontweight="bold")

    ax1 = fig.add_subplot(grid[1, :8])
    ax1.plot(monthly["month"], monthly["revenue"] / 1_000, color=TEAL, linewidth=2.5, marker="o")
    partial = monthly[monthly["is_partial_month"] == 1]
    ax1.scatter(
        partial["month"], partial["revenue"] / 1_000, facecolor="white",
        edgecolor=AMBER, linewidth=2, s=70, zorder=4,
    )
    ax1.set_title("Monthly revenue", loc="left")
    ax1.text(
        0.01, 0.92, "Open markers indicate partial months", transform=ax1.transAxes,
        color=SLATE, fontsize=9,
    )
    ax1.set_ylabel("£ thousands")
    ax1.set_xlabel("")
    ax1.tick_params(axis="x", rotation=30)
    sns.despine(ax=ax1)

    ax2 = fig.add_subplot(grid[1, 8:])
    ax2.barh(
        segments["segment"], segments["revenue"] / 1_000_000,
        color=[RED if value == "At Risk" else MINT for value in segments["segment"]],
    )
    ax2.set_title("Revenue by RFM segment", loc="left")
    ax2.set_xlabel("£ millions")
    ax2.set_ylabel("")
    ax2.grid(axis="y", visible=False)
    sns.despine(ax=ax2, left=True)

    ax3 = fig.add_subplot(grid[2, :6])
    ax3.bar(concentration["revenue_decile"], concentration["revenue_share_pct"], color=MINT)
    ax3.plot(
        concentration["revenue_decile"], concentration["cumulative_revenue_share_pct"],
        color=NAVY, marker="o", linewidth=2,
    )
    ax3.set_title("Customer revenue concentration", loc="left")
    ax3.set_xlabel("Revenue decile (1 = highest)")
    ax3.set_ylabel("Revenue share (%)")
    ax3.set_xticks(range(1, 11))
    sns.despine(ax=ax3)

    ax4 = fig.add_subplot(grid[2, 6:])
    ax4.axis("off")
    findings = [
        f"{summary['one_order_customer_pct']:.1f}% of customers purchased only once.",
        f"Median time to a second order was {summary['median_days_to_second_order']} days.",
        f"The top customer decile generated {summary['top_decile_revenue_share_pct']:.1f}% of revenue.",
        f"At-risk customers previously generated £{summary['at_risk_historical_revenue'] / 1_000_000:.2f}M.",
    ]
    ax4.text(0, 1.0, "Key findings", color=NAVY, fontsize=15, fontweight="bold", va="top")
    for index, finding in enumerate(findings):
        ax4.text(0.0, 0.79 - index * 0.19, f"{index + 1}.  {finding}", color=NAVY, fontsize=12, va="top")

    save_figure(fig, "executive_dashboard.png")


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError("Run scripts/build_database.py before this script.")
    set_plot_style()
    results = run_queries()
    plot_monthly_revenue(results["monthly_revenue"])
    plot_segments(results["rfm_segments"])
    plot_cohort_retention(results["cohort_retention"])
    plot_revenue_concentration(results["revenue_concentration"])
    plot_top_products(results["top_products"])
    summary = build_summary(results)
    create_executive_dashboard(results, summary)
    (ROOT / "outputs" / "summary_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
