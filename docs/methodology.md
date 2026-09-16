# Methodology

## 1. Acquire and preserve the source

The pipeline downloads the 22.6 MB workbook from the UCI Machine Learning Repository. Raw files are excluded from version control because the project can reproduce them from the cited source.

## 2. Profile data quality

The source contains 541,909 lines. Profiling identified:

- 135,080 lines without a customer ID;
- 9,288 cancellation lines;
- 10,624 lines with nonpositive quantity; and
- 2,517 lines with nonpositive price.

These categories overlap, so their counts should not be added together.

## 3. Define the analysis population

Customer and revenue analysis uses valid sales lines: non-cancelled rows with positive quantity, positive price, customer ID, and description. This produces 397,884 valid sales lines.

The full source remains in `transaction_lines`, allowing data-quality and cancellation analysis without mixing those events into sales KPIs.

## 4. Create an analytical data model

Pandas creates customer, product, order, and order-item tables. SQLite provides a portable relational database and supports all SQL techniques used in the project.

## 5. Answer business questions

The SQL analysis covers:

1. KPI summary and data quality
2. Monthly revenue and month-over-month change
3. Purchase-frequency distribution
4. Time to second order
5. Stable top products and product anomalies
6. Country performance
7. Customer revenue concentration
8. RFM customer segments
9. Monthly cohort retention

## 6. Apply analytical safeguards

- Partial first and final months are flagged.
- Product rankings exclude service codes and products with fewer than 50 orders.
- High-revenue products supported by five or fewer orders are reported as anomalies.
- Recommendations are framed as tests when the data cannot establish causality.
- Revenue and cancelled value are not described as profit impact.

## 7. Translate findings into decisions

Recommendations prioritize retention timing, high-value at-risk customers, seasonal planning, customer concentration, and stronger transaction controls. Each action includes a measurement approach or an explicit validation requirement.

