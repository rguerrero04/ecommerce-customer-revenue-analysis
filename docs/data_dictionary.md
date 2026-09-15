# Data dictionary

## Source fields

| Field | Type | Description |
|---|---|---|
| `invoice_no` | Text | Source invoice identifier. Values beginning with `C` indicate cancellations. |
| `stock_code` | Text | Product or service code. Kept as text to preserve alphanumeric values. |
| `description` | Text | Product description. |
| `quantity` | Integer | Units on the transaction line. Negative values generally indicate returns or adjustments. |
| `invoice_date` | Datetime | Transaction timestamp. |
| `unit_price` | Decimal | Unit price in pounds sterling. |
| `customer_id` | Text | Customer identifier. Stored as text because it is an identifier, not a measure. |
| `country` | Text | Customer country recorded on the transaction. |

## Engineered fields

| Field | Grain | Definition |
|---|---|---|
| `line_revenue` | Transaction line | `quantity * unit_price` |
| `is_cancellation` | Transaction line | 1 when `invoice_no` begins with `C`; otherwise 0 |
| `is_valid_sale` | Transaction line | 1 for non-cancelled, positive-value, customer-linked lines with a description |
| `order_id` | Order | Composite of invoice number, customer ID, and invoice timestamp |
| `order_revenue` | Order | Sum of valid line revenue within an order |
| `recency_days` | Customer | Days between a customer's most recent order and the day after the latest order in the dataset |
| `frequency` | Customer | Count of valid orders |
| `monetary` | Customer | Sum of valid order revenue |
| `cohort_month` | Customer | Calendar month of the customer's first valid purchase |
| `month_number` | Cohort activity | Whole months since cohort month, where 0 is the acquisition month |

## Modeled tables

| Table | Grain | Purpose |
|---|---|---|
| `transaction_lines` | One source transaction line | Preserves raw business events and data-quality flags |
| `customers` | One customer | Stores country and first/last purchase dates |
| `products` | One stock code | Stores the most frequently observed description per product |
| `orders` | One composite order ID | Supports customer, time, and geographic analysis |
| `order_items` | One valid sales line | Supports product and basket analysis |

## Important modeling choice

The source reuses some invoice numbers across timestamps one minute apart. The project therefore uses a composite `order_id` rather than treating `invoice_no` alone as a guaranteed primary key.

