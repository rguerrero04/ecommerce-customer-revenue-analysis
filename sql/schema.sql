-- SQLite schema created by scripts/build_database.py.
-- The raw source stays at line-item grain in transaction_lines.

CREATE TABLE transaction_lines (
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL,
    invoice_date TEXT NOT NULL,
    unit_price REAL NOT NULL,
    customer_id TEXT,
    country TEXT NOT NULL,
    line_revenue REAL NOT NULL,
    is_cancellation INTEGER NOT NULL,
    is_valid_sale INTEGER NOT NULL
);

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    country TEXT NOT NULL,
    first_purchase_date TEXT NOT NULL,
    last_purchase_date TEXT NOT NULL
);

CREATE TABLE products (
    stock_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    country TEXT NOT NULL,
    line_count INTEGER NOT NULL,
    units INTEGER NOT NULL,
    order_revenue REAL NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_id TEXT NOT NULL,
    invoice_no TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    line_revenue REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (stock_code) REFERENCES products(stock_code)
);
