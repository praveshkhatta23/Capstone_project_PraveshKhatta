-- Run against the raw, uncleaned data after schema.sql and seed_data.sql.
-- (a) Expected: total_orders=180, total_revenue=99860.20, avg_order_value=554.78
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_revenue,
       ROUND(AVG(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS avg_order_value
FROM orders o JOIN products p ON p.product_id = o.product_id;

-- (b) Expected: (180, 165, 15)
SELECT COUNT(*) AS all_orders, COUNT(rating) AS rated_orders,
       COUNT(*) - COUNT(rating) AS unrated_orders
FROM orders;

-- (c1) Expected: C045 | Vihaan
SELECT c.customer_id, c.name
FROM customers c LEFT JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
HAVING COUNT(o.order_id) = 0;

-- (c2) Independent verification; expected same row: C045 | Vihaan
SELECT customer_id, name FROM customers
WHERE customer_id NOT IN (SELECT DISTINCT customer_id FROM orders);

-- (d) Expected rows: Jaipur (19,8,42.1), Lucknow (49,15,30.6), Bangalore (33,8,24.2)
SELECT c.city, COUNT(*) AS total_orders,
       SUM(CASE WHEN o.returned = 1 THEN 1 ELSE 0 END) AS returned_orders,
       ROUND(100.0 * SUM(CASE WHEN o.returned = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS return_rate_pct
FROM orders o JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.city
HAVING return_rate_pct > 20
ORDER BY return_rate_pct DESC;

-- (e1) Expected top 5: C043 Reyansh 12920.00; C026 Isha 8371.60; C008 Meera 4564.60; C011 Arjun 4111.00; C042 Sanya 3785.00
-- customer_id ASC is the deterministic tie-breaker when spend is equal.
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o JOIN products p ON p.product_id=o.product_id
JOIN customers c ON c.customer_id=o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC LIMIT 5;

-- (e2) Expected ranks 3-5 from the same ordering: C008, C011, C042
SELECT c.customer_id, c.name,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS total_spend
FROM orders o JOIN products p ON p.product_id=o.product_id
JOIN customers c ON c.customer_id=o.customer_id
GROUP BY c.customer_id, c.name
ORDER BY total_spend DESC, c.customer_id ASC LIMIT 3 OFFSET 2;

-- (f) Expected: Haircare (54,44956.10), Skincare (60,27346.00), Babycare (30,16805.00), PersonalCare (36,10753.10)
SELECT p.category, COUNT(*) AS order_count,
       ROUND(SUM(o.quantity * p.price * (1 - COALESCE(o.discount_pct, 0) / 100.0)), 2) AS category_revenue
FROM orders o JOIN products p ON p.product_id=o.product_id
JOIN customers c ON c.customer_id=o.customer_id
GROUP BY p.category ORDER BY category_revenue DESC;

-- (g) Expected: 10 rows
SELECT customer_id, name FROM customers WHERE name LIKE 'A%' ORDER BY customer_id;

-- (h) Expected distinct values: Ad, Organic, Referral, Social
SELECT DISTINCT acquisition_source FROM customers ORDER BY acquisition_source;

-- (i) Run once on a fresh database; expected counts Gold=28, Silver=17.
ALTER TABLE customers ADD COLUMN loyalty_tier VARCHAR(10);
UPDATE customers SET loyalty_tier = CASE WHEN city_tier = 1 THEN 'Gold' ELSE 'Silver' END;
SELECT loyalty_tier, COUNT(*) AS customer_count FROM customers GROUP BY loyalty_tier ORDER BY loyalty_tier;
