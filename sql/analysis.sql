-- Each query begins with a marker consumed by scripts/run_analysis.py.
-- SQLite syntax is used so the full project runs without a database server.

-- query: data_quality
SELECT
    COUNT(*) AS raw_line_count,
    COUNT(DISTINCT invoice_no) AS invoice_count,
    SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS missing_customer_id_lines,
    SUM(is_cancellation) AS cancellation_lines,
    SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END) AS nonpositive_quantity_lines,
    SUM(CASE WHEN unit_price <= 0 THEN 1 ELSE 0 END) AS nonpositive_price_lines,
    SUM(is_valid_sale) AS valid_sales_lines
FROM transaction_lines;

-- query: kpi_summary
WITH customer_order_counts AS (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
),
order_kpis AS (
    SELECT
        SUM(order_revenue) AS revenue,
        COUNT(*) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        AVG(order_revenue) AS average_order_value,
        AVG(units) AS average_units_per_order
    FROM orders
),
customer_kpis AS (
    SELECT
        100.0 * SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) / COUNT(*)
            AS repeat_customer_rate_pct
    FROM customer_order_counts
),
cancelled_value AS (
    SELECT ABS(SUM(line_revenue)) AS cancelled_value
    FROM transaction_lines
    WHERE is_cancellation = 1
)
SELECT
    ROUND(o.revenue, 2) AS revenue,
    o.orders,
    o.customers,
    ROUND(o.average_order_value, 2) AS average_order_value,
    ROUND(o.average_units_per_order, 2) AS average_units_per_order,
    ROUND(c.repeat_customer_rate_pct, 2) AS repeat_customer_rate_pct,
    ROUND((SELECT cancelled_value FROM cancelled_value), 2) AS cancelled_value
FROM order_kpis o
CROSS JOIN customer_kpis c;

-- query: monthly_revenue
WITH monthly AS (
    SELECT
        strftime('%Y-%m', invoice_date) AS order_month,
        ROUND(SUM(order_revenue), 2) AS revenue,
        COUNT(*) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        ROUND(AVG(order_revenue), 2) AS average_order_value
    FROM orders
    GROUP BY strftime('%Y-%m', invoice_date)
),
with_previous AS (
    SELECT
        *,
        LAG(revenue) OVER (ORDER BY order_month) AS previous_month_revenue
    FROM monthly
)
SELECT
    order_month,
    revenue,
    orders,
    customers,
    average_order_value,
    ROUND(100.0 * (revenue - previous_month_revenue) /
          NULLIF(previous_month_revenue, 0), 2) AS month_over_month_pct,
    CASE WHEN order_month IN ('2010-12', '2011-12') THEN 1 ELSE 0 END AS is_partial_month
FROM with_previous
ORDER BY order_month;

-- query: customer_purchase_frequency
WITH customer_orders AS (
    SELECT
        customer_id,
        COUNT(*) AS order_count,
        SUM(order_revenue) AS customer_revenue
    FROM orders
    GROUP BY customer_id
)
SELECT
    CASE
        WHEN order_count = 1 THEN '1 order'
        WHEN order_count BETWEEN 2 AND 4 THEN '2-4 orders'
        WHEN order_count BETWEEN 5 AND 9 THEN '5-9 orders'
        ELSE '10+ orders'
    END AS purchase_frequency,
    COUNT(*) AS customers,
    ROUND(SUM(customer_revenue), 2) AS revenue,
    ROUND(AVG(customer_revenue), 2) AS revenue_per_customer
FROM customer_orders
GROUP BY purchase_frequency
ORDER BY MIN(order_count);

-- query: reorder_timing
WITH ranked_orders AS (
    SELECT
        customer_id,
        order_id,
        invoice_no,
        invoice_date,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY invoice_date, order_id
        ) AS purchase_number
    FROM orders
),
first_two AS (
    SELECT
        customer_id,
        MAX(CASE WHEN purchase_number = 1 THEN invoice_date END) AS first_order_date,
        MAX(CASE WHEN purchase_number = 2 THEN invoice_date END) AS second_order_date
    FROM ranked_orders
    WHERE purchase_number <= 2
    GROUP BY customer_id
)
SELECT
    customer_id,
    first_order_date,
    second_order_date,
    CAST(julianday(second_order_date) - julianday(first_order_date) AS INTEGER) AS days_to_second_order
FROM first_two
WHERE second_order_date IS NOT NULL
ORDER BY days_to_second_order, customer_id;

-- query: top_products
WITH product_sales AS (
    SELECT
        oi.stock_code,
        p.description,
        ROUND(SUM(oi.line_revenue), 2) AS revenue,
        SUM(oi.quantity) AS units,
        COUNT(DISTINCT oi.order_id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers
    FROM order_items oi
    JOIN products p ON oi.stock_code = p.stock_code
    JOIN orders o ON oi.order_id = o.order_id
    WHERE UPPER(oi.stock_code) NOT IN ('POST', 'DOT', 'M', 'BANK CHARGES')
    GROUP BY oi.stock_code, p.description
    HAVING COUNT(DISTINCT oi.order_id) >= 50
),
ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY revenue DESC) AS revenue_rank
    FROM product_sales
)
SELECT *
FROM ranked
WHERE revenue_rank <= 15
ORDER BY revenue_rank, stock_code;

-- query: product_anomalies
WITH product_sales AS (
    SELECT
        oi.stock_code,
        p.description,
        ROUND(SUM(oi.line_revenue), 2) AS revenue,
        SUM(oi.quantity) AS units,
        COUNT(DISTINCT oi.order_id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers
    FROM order_items oi
    JOIN products p ON oi.stock_code = p.stock_code
    JOIN orders o ON oi.order_id = o.order_id
    GROUP BY oi.stock_code, p.description
)
SELECT *
FROM product_sales
WHERE revenue >= 25000 AND orders <= 5
ORDER BY revenue DESC;

-- query: country_performance
WITH country_sales AS (
    SELECT
        country,
        ROUND(SUM(order_revenue), 2) AS revenue,
        COUNT(*) AS orders,
        COUNT(DISTINCT customer_id) AS customers,
        ROUND(AVG(order_revenue), 2) AS average_order_value
    FROM orders
    GROUP BY country
),
total_sales AS (
    SELECT SUM(order_revenue) AS total_revenue FROM orders
),
customer_repeat AS (
    SELECT
        country,
        customer_id,
        COUNT(*) AS order_count
    FROM orders
    GROUP BY country, customer_id
)
SELECT
    cs.*,
    ROUND(100.0 * SUM(CASE WHEN cr.order_count >= 2 THEN 1 ELSE 0 END) /
          COUNT(*), 2) AS repeat_customer_rate_pct,
    ROUND(100.0 * cs.revenue / ts.total_revenue, 2) AS revenue_share_pct
FROM country_sales cs
JOIN customer_repeat cr ON cs.country = cr.country
CROSS JOIN total_sales ts
GROUP BY cs.country, cs.revenue, cs.orders, cs.customers, cs.average_order_value, ts.total_revenue
HAVING cs.customers >= 10
ORDER BY cs.revenue DESC;

-- query: revenue_concentration
WITH customer_revenue AS (
    SELECT
        customer_id,
        SUM(order_revenue) AS revenue,
        COUNT(*) AS orders
    FROM orders
    GROUP BY customer_id
),
deciles AS (
    SELECT
        *,
        NTILE(10) OVER (ORDER BY revenue DESC) AS revenue_decile
    FROM customer_revenue
),
decile_summary AS (
    SELECT
        revenue_decile,
        COUNT(*) AS customers,
        ROUND(SUM(revenue), 2) AS revenue,
        SUM(orders) AS orders
    FROM deciles
    GROUP BY revenue_decile
)
SELECT
    revenue_decile,
    customers,
    revenue,
    orders,
    ROUND(100.0 * revenue / SUM(revenue) OVER (), 2) AS revenue_share_pct,
    ROUND(100.0 * SUM(revenue) OVER (ORDER BY revenue_decile) /
          SUM(revenue) OVER (), 2) AS cumulative_revenue_share_pct
FROM decile_summary
ORDER BY revenue_decile;

-- query: rfm_segments
WITH analysis_date AS (
    SELECT date(MAX(invoice_date), '+1 day') AS as_of_date FROM orders
),
customer_metrics AS (
    SELECT
        o.customer_id,
        CAST(julianday(a.as_of_date) - julianday(MAX(o.invoice_date)) AS INTEGER) AS recency_days,
        COUNT(*) AS frequency,
        ROUND(SUM(o.order_revenue), 2) AS monetary
    FROM orders o
    CROSS JOIN analysis_date a
    GROUP BY o.customer_id, a.as_of_date
),
scored AS (
    SELECT
        *,
        NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(4) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(4) OVER (ORDER BY monetary ASC) AS m_score
    FROM customer_metrics
),
segmented AS (
    SELECT
        *,
        CASE
            WHEN r_score = 4 AND f_score = 4 AND m_score = 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
            WHEN r_score >= 3 AND f_score <= 2 THEN 'New / Promising'
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating'
            ELSE 'Potential Loyalists'
        END AS segment
    FROM scored
)
SELECT
    segment,
    COUNT(*) AS customers,
    ROUND(SUM(monetary), 2) AS revenue,
    ROUND(AVG(monetary), 2) AS revenue_per_customer,
    ROUND(AVG(recency_days), 1) AS average_recency_days,
    ROUND(AVG(frequency), 1) AS average_orders
FROM segmented
GROUP BY segment
ORDER BY revenue DESC;

-- query: cohort_retention
WITH first_purchase AS (
    SELECT
        customer_id,
        strftime('%Y-%m-01', MIN(invoice_date)) AS cohort_month
    FROM orders
    GROUP BY customer_id
),
activity AS (
    SELECT DISTINCT
        customer_id,
        strftime('%Y-%m-01', invoice_date) AS activity_month
    FROM orders
),
cohort_activity AS (
    SELECT
        f.cohort_month,
        a.activity_month,
        ((CAST(strftime('%Y', a.activity_month) AS INTEGER) -
          CAST(strftime('%Y', f.cohort_month) AS INTEGER)) * 12 +
         (CAST(strftime('%m', a.activity_month) AS INTEGER) -
          CAST(strftime('%m', f.cohort_month) AS INTEGER))) AS month_number,
        COUNT(DISTINCT a.customer_id) AS active_customers
    FROM first_purchase f
    JOIN activity a ON f.customer_id = a.customer_id
    GROUP BY f.cohort_month, a.activity_month
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM first_purchase
    GROUP BY cohort_month
)
SELECT
    ca.cohort_month,
    ca.month_number,
    ca.active_customers,
    cs.cohort_size,
    ROUND(100.0 * ca.active_customers / cs.cohort_size, 2) AS retention_rate_pct
FROM cohort_activity ca
JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
WHERE ca.month_number BETWEEN 0 AND 11
ORDER BY ca.cohort_month, ca.month_number;
