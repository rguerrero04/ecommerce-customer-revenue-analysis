"""Download, clean, and model the UCI Online Retail dataset in SQLite."""

from __future__ import annotations

import sqlite3
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
OUTPUT_TABLES = ROOT / "outputs" / "tables"
ZIP_PATH = RAW_DIR / "online_retail.zip"
XLSX_PATH = RAW_DIR / "Online Retail.xlsx"
DB_PATH = PROCESSED_DIR / "ecommerce.db"
DATA_URL = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"


def acquire_data() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not ZIP_PATH.exists():
        print("Downloading UCI Online Retail dataset...")
        urllib.request.urlretrieve(DATA_URL, ZIP_PATH)
    if not XLSX_PATH.exists():
        with zipfile.ZipFile(ZIP_PATH) as archive:
            archive.extract("Online Retail.xlsx", RAW_DIR)


def load_and_clean() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(XLSX_PATH)
    raw.columns = [
        "invoice_no",
        "stock_code",
        "description",
        "quantity",
        "invoice_date",
        "unit_price",
        "customer_id",
        "country",
    ]

    raw["invoice_no"] = raw["invoice_no"].astype("string").str.strip()
    raw["stock_code"] = raw["stock_code"].astype("string").str.strip()
    raw["description"] = raw["description"].astype("string").str.strip()
    raw["country"] = raw["country"].astype("string").str.strip()
    raw["customer_id"] = raw["customer_id"].astype("Int64").astype("string")
    raw["invoice_date"] = pd.to_datetime(raw["invoice_date"])
    raw["line_revenue"] = raw["quantity"] * raw["unit_price"]
    raw["is_cancellation"] = raw["invoice_no"].str.upper().str.startswith("C").astype(int)
    raw["is_valid_sale"] = (
        (raw["is_cancellation"] == 0)
        & (raw["quantity"] > 0)
        & (raw["unit_price"] > 0)
        & raw["customer_id"].notna()
        & raw["description"].notna()
    ).astype(int)

    valid = raw.loc[raw["is_valid_sale"] == 1].copy()
    return raw, valid


def build_model(valid: pd.DataFrame) -> dict[str, pd.DataFrame]:
    valid = valid.copy()
    valid["order_id"] = (
        valid["invoice_no"]
        + "_"
        + valid["customer_id"]
        + "_"
        + valid["invoice_date"].dt.strftime("%Y%m%d%H%M%S")
    )
    orders = (
        valid.groupby(
            ["order_id", "invoice_no", "customer_id", "invoice_date", "country"],
            as_index=False,
        )
        .agg(
            line_count=("stock_code", "size"),
            units=("quantity", "sum"),
            order_revenue=("line_revenue", "sum"),
        )
    )

    customer_country = (
        orders.sort_values("invoice_date")
        .groupby("customer_id", as_index=False)
        .agg(
            country=("country", "last"),
            first_purchase_date=("invoice_date", "min"),
            last_purchase_date=("invoice_date", "max"),
        )
    )

    descriptions = (
        valid.groupby(["stock_code", "description"], as_index=False)
        .size()
        .sort_values(["stock_code", "size", "description"], ascending=[True, False, True])
        .drop_duplicates("stock_code")
    )
    products = descriptions[["stock_code", "description"]].copy()
    order_items = valid[
        ["order_id", "invoice_no", "stock_code", "quantity", "unit_price", "line_revenue"]
    ].copy()

    return {
        "customers": customer_country,
        "products": products,
        "orders": orders,
        "order_items": order_items,
    }


def write_database(raw: pd.DataFrame, model: dict[str, pd.DataFrame]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TABLES.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    sqlite_raw = raw.copy()
    sqlite_raw["invoice_date"] = sqlite_raw["invoice_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    sqlite_raw = sqlite_raw.where(pd.notna(sqlite_raw), None)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        sqlite_raw.to_sql("transaction_lines", conn, index=False, if_exists="replace")
        for table_name, frame in model.items():
            to_write = frame.copy()
            for column in to_write.select_dtypes(include=["datetime64[ns]"]).columns:
                to_write[column] = to_write[column].dt.strftime("%Y-%m-%d %H:%M:%S")
            to_write.to_sql(table_name, conn, index=False, if_exists="replace")

        conn.executescript(
            """
            CREATE UNIQUE INDEX idx_orders_order_id ON orders(order_id);
            CREATE INDEX idx_orders_invoice ON orders(invoice_no);
            CREATE INDEX idx_orders_customer_date ON orders(customer_id, invoice_date);
            CREATE INDEX idx_orders_country ON orders(country);
            CREATE INDEX idx_items_order ON order_items(order_id);
            CREATE INDEX idx_items_invoice ON order_items(invoice_no);
            CREATE INDEX idx_items_stock ON order_items(stock_code);
            CREATE INDEX idx_lines_invoice ON transaction_lines(invoice_no);
            CREATE INDEX idx_lines_customer ON transaction_lines(customer_id);
            """
        )

    quality = pd.DataFrame(
        {
            "metric": [
                "Raw transaction lines",
                "Valid sales lines",
                "Excluded lines",
                "Missing customer ID lines",
                "Cancellation lines",
                "Nonpositive quantity lines",
                "Nonpositive price lines",
            ],
            "value": [
                len(raw),
                int(raw["is_valid_sale"].sum()),
                int((raw["is_valid_sale"] == 0).sum()),
                int(raw["customer_id"].isna().sum()),
                int(raw["is_cancellation"].sum()),
                int((raw["quantity"] <= 0).sum()),
                int((raw["unit_price"] <= 0).sum()),
            ],
        }
    )
    quality.to_csv(OUTPUT_TABLES / "data_quality_summary.csv", index=False)


def main() -> None:
    acquire_data()
    raw, valid = load_and_clean()
    model = build_model(valid)
    write_database(raw, model)
    print(f"Created {DB_PATH}")
    print(f"Rows: raw={len(raw):,}, valid_sales={len(valid):,}, orders={len(model['orders']):,}")


if __name__ == "__main__":
    main()
