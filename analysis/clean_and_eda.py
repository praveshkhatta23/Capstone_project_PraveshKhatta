"""Pandas cleaning, EDA and findings export for the Mamaearth capstone.
Run from any directory: python analysis/clean_and_eda.py
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NARRATOR = ROOT / "narrator"
NARRATOR.mkdir(exist_ok=True)
NATURAL_KEY = ["customer_id", "product_id", "order_date", "quantity", "discount_pct", "payment_method", "rating", "returned"]

def money(v): return round(float(v), 2)
def strength(r):
    a = abs(float(r))
    if a <= 0.19: return "negligible"
    if a <= 0.39: return "weak"
    if a <= 0.69: return "moderate"
    return "strong"

def main():
    customers = pd.read_csv(DATA / "customers.csv")
    products = pd.read_csv(DATA / "products.csv")
    orders = pd.read_csv(DATA / "orders.csv")
    print("TASK 1 — LOAD AND INSPECT")
    print("customers.shape:", customers.shape)
    print("products.shape:", products.shape)
    print("orders.shape BEFORE cleaning:", orders.shape)
    assert orders.shape == (180, 9)

    print("\nTASK 2 — PAYMENT METHOD STANDARDIZATION")
    print("Raw unique values:", sorted(orders["payment_method"].dropna().unique().tolist()))
    print("Raw unique count:", orders["payment_method"].nunique(dropna=True))
    orders["payment_method"] = orders["payment_method"].astype("string").str.strip().str.upper()
    print("Standardized unique values:", sorted(orders["payment_method"].dropna().unique().tolist()))
    print("Standardized counts:\n", orders["payment_method"].value_counts(dropna=False).sort_index().to_string())

    print("\nTASK 3 — DUPLICATE ORDER REMOVAL")
    duplicate_mask = orders.duplicated(subset=NATURAL_KEY, keep="first")
    duplicate_rows = orders.loc[duplicate_mask].copy()
    duplicate_ids = duplicate_rows["order_id"].tolist()
    print("Duplicate rows flagged:", int(duplicate_mask.sum()))
    print("Dropped order_id values:", duplicate_ids)
    orders_clean = orders.loc[~duplicate_mask].copy()
    print("orders_clean.shape:", orders_clean.shape)
    assert duplicate_ids == ["O0176", "O0177", "O0178", "O0179", "O0180"]
    assert orders_clean.shape == (175, 9)

    print("\nTASK 4 — MISSING-VALUE IMPUTATION")
    orders_clean["discount_pct"] = pd.to_numeric(orders_clean["discount_pct"], errors="coerce")
    orders_clean["rating"] = pd.to_numeric(orders_clean["rating"], errors="coerce")
    missing_discount = int(orders_clean["discount_pct"].isna().sum())
    missing_rating = int(orders_clean["rating"].isna().sum())
    rating_median = float(orders_clean["rating"].median())
    print("Missing discount_pct rows:", missing_discount)
    print("Median of non-null ratings before imputation:", rating_median)
    print("Missing rating rows:", missing_rating)
    orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
    orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
    print("Null counts after imputation:", orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())
    assert missing_discount == 12 and missing_rating == 15 and rating_median == 3.0

    print("\nTASK 5 — MERGE AND RECONCILE")
    # Independently compute raw revenue from the untouched raw order rows; NULL discounts mean 0%.
    raw_for_rev = orders.copy()
    raw_for_rev["discount_pct"] = pd.to_numeric(raw_for_rev["discount_pct"], errors="coerce").fillna(0)
    raw_for_rev["quantity"] = pd.to_numeric(raw_for_rev["quantity"], errors="coerce")
    raw_for_rev = raw_for_rev.merge(products[["product_id", "price"]], on="product_id", how="left", validate="many_to_one")
    raw_for_rev["order_value"] = raw_for_rev["quantity"] * raw_for_rev["price"] * (1 - raw_for_rev["discount_pct"] / 100)
    raw_revenue = money(raw_for_rev["order_value"].sum())
    # Check duplicate delta independently using the five rows dropped by the natural-key rule.
    duplicate_rev = duplicate_rows.copy()
    duplicate_rev["discount_pct"] = pd.to_numeric(duplicate_rev["discount_pct"], errors="coerce").fillna(0)
    duplicate_rev["quantity"] = pd.to_numeric(duplicate_rev["quantity"], errors="coerce")
    duplicate_rev = duplicate_rev.merge(products[["product_id", "price"]], on="product_id", how="left", validate="many_to_one")
    duplicate_delta = money((duplicate_rev["quantity"] * duplicate_rev["price"] * (1 - duplicate_rev["discount_pct"] / 100)).sum())

    merged = orders_clean.merge(products, on="product_id", how="left", validate="many_to_one")
    merged = merged.merge(customers, on="customer_id", how="left", validate="many_to_one")
    merged["order_date"] = pd.to_datetime(merged["order_date"], errors="raise")
    merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
    cleaned_revenue = money(merged["order_value"].sum())
    print("Merged cleaned shape:", merged.shape)
    print("Raw total revenue (NULL discount treated as 0%):", f"{raw_revenue:.2f}")
    print("Cleaned total revenue across 175 rows:", f"{cleaned_revenue:.2f}")
    print("Combined order_value of dropped duplicate rows:", f"{duplicate_delta:.2f}")
    print("Reconciliation: Raw revenue is ₹99,860.20 and cleaned revenue is ₹97,358.30, a decrease of ₹2,501.90. The decrease is exactly the combined order_value of duplicate rows O0176–O0180, which are removed using the natural key. Filling missing discount_pct values with 0 and missing rating values with the median does not change order_value for any retained row; the revenue delta is attributable to duplicate removal, not imputation.")
    assert (raw_revenue, cleaned_revenue, duplicate_delta) == (99860.20, 97358.30, 2501.90)

    print("\nTASK 6 — IQR OUTLIER DETECTION ON QUANTITY")
    q1, q3 = merged["quantity"].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
    outliers = merged.loc[merged["is_outlier"], ["order_id", "quantity"]]
    print({"Q1": float(q1), "Q3": float(q3), "IQR": float(iqr), "lower": float(lower), "upper": float(upper)})
    print("Outlier rows (flagged, not removed):\n", outliers.to_string(index=False))
    assert outliers["order_id"].tolist() == ["O0011", "O0098"]

    print("\nTASK 7 — HYPOTHESIS: DOES COD HAVE A HIGHER RETURN RATE?")
    print("Hypothesis: COD orders have a higher return rate than CARD and UPI orders.")
    payment = merged.groupby("payment_method")["returned"].agg(["count", "mean"]).reset_index()
    payment["return_rate_pct"] = (payment["mean"] * 100).round(1)
    print(payment[["payment_method", "count", "return_rate_pct"]].sort_values("payment_method").to_string(index=False))
    print("Hypothesis verdict: Confirmed — COD has the highest observed return rate.")
    assert dict(zip(payment.payment_method, payment.return_rate_pct)) == {"CARD": 14.7, "COD": 44.4, "UPI": 18.9}

    print("\nTASK 8 — PAYMENT METHOD × CITY TIER SEGMENTATION")
    segment = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"]).reset_index()
    segment["return_rate_pct"] = (segment["mean"] * 100).round(1)
    print(segment[["payment_method", "city_tier", "count", "return_rate_pct"]].sort_values(["payment_method", "city_tier"]).to_string(index=False))
    cod_tier2 = segment[(segment.payment_method == "COD") & (segment.city_tier == 2)].iloc[0]
    print(f"Highest-risk segment: COD + Tier-2 cities at {cod_tier2.return_rate_pct:.1f}%.")
    cod_tier1 = segment[(segment.payment_method == "COD") & (segment.city_tier == 1)].iloc[0]
    print(f"COD Tier-1: {int(cod_tier1['count'])} orders at {cod_tier1.return_rate_pct:.1f}%; COD Tier-2: {int(cod_tier2['count'])} orders at {cod_tier2.return_rate_pct:.1f}%.")
    assert int(cod_tier1["count"]) == 32 and cod_tier1.return_rate_pct == 37.5
    assert int(cod_tier2["count"]) == 22 and cod_tier2.return_rate_pct == 54.5

    print("\nTASK 9 — CORRELATION ANALYSIS")
    corr_cols = ["rating", "returned", "discount_pct", "quantity"]
    corr = merged[corr_cols].corr()
    print(corr.round(4).to_string())
    correlation_pairs = []
    for i, a in enumerate(corr_cols):
        for b in corr_cols[i+1:]:
            r = float(corr.loc[a,b])
            band = strength(r)
            correlation_pairs.append({"variable_1": a, "variable_2": b, "correlation": round(r, 4), "strength": band})
            print(f"{a} vs {b}: r={r:.4f} — {band}")
    discount_return = float(corr.loc["discount_pct", "returned"])
    print(f'Hypothesis "higher discounts reduce returns": Busted (discount_pct vs returned correlation = {discount_return:.4f}; negligible).')
    assert all(x["strength"] == "negligible" for x in correlation_pairs)

    print("\nTASK 10 — MONTHLY REVENUE, INCLUDING AND EXCLUDING QUANTITY OUTLIERS")
    merged["month"] = merged["order_date"].dt.to_period("M").astype(str)
    monthly = merged.groupby("month").apply(lambda g: pd.Series({
        "revenue_including_outliers": g["order_value"].sum(),
        "revenue_excluding_outliers": g.loc[~g["is_outlier"], "order_value"].sum()
    }), include_groups=False).reset_index()
    monthly[["revenue_including_outliers", "revenue_excluding_outliers"]] = monthly[["revenue_including_outliers", "revenue_excluding_outliers"]].round(2)
    print("Monthly revenue including outliers:\n", monthly[["month", "revenue_including_outliers"]].to_string(index=False))
    print("Monthly revenue excluding outliers (corrected):\n", monthly[["month", "revenue_excluding_outliers"]].to_string(index=False))
    peak = monthly.loc[monthly["revenue_excluding_outliers"].idxmax()]
    inflated_peak = monthly.loc[monthly["revenue_including_outliers"].idxmax()]
    print("Interpretation: January's apparent lead is an artifact of two bulk orders landing in January (O0011 on 2026-01-28 and O0098 on 2026-01-10). March is the genuine peak month once those two flagged orders are excluded.")
    assert peak["month"] == "2026-03" and money(peak["revenue_excluding_outliers"]) == 20318.90
    assert inflated_peak["month"] == "2026-01" and money(inflated_peak["revenue_including_outliers"]) == 29582.10

    # Export analysis outputs; all generated from raw CSVs at runtime.
    merged.to_csv(DATA / "cleaned_merged.csv", index=False)
    payment[["payment_method", "count", "return_rate_pct"]].to_csv(DATA / "return_rate_by_payment.csv", index=False)
    monthly.to_csv(DATA / "monthly_revenue.csv", index=False)
    segment.to_csv(DATA / "return_rate_by_payment_city_tier.csv", index=False)
    findings = {
        "cleaned_total_revenue_inr": cleaned_revenue,
        "raw_total_revenue_inr": raw_revenue,
        "duplicate_reconciliation_delta_inr": duplicate_delta,
        "return_rate_by_payment": {str(r.payment_method): float(r.return_rate_pct) for r in payment.itertuples()},
        "highest_risk_segment": {"payment_method": "COD", "city_tier": 2, "return_rate_pct": float(cod_tier2.return_rate_pct)},
        "true_peak_month": {"month": str(peak["month"]), "revenue_inr": money(peak["revenue_excluding_outliers"])},
        "outlier_inflated_month": {"month": str(inflated_peak["month"]), "apparent_revenue_inr": money(inflated_peak["revenue_including_outliers"]), "corrected_revenue_inr": money(monthly.loc[monthly.month == inflated_peak.month, "revenue_excluding_outliers"].iloc[0])},
        "source_row_counts": {"customers": int(len(customers)), "products": int(len(products)), "orders": int(len(orders))},
        "cleaned_order_count": int(len(merged)),
        "duplicate_rows_dropped": int(len(duplicate_ids)),
        "duplicate_order_ids_dropped": duplicate_ids,
        "missing_discount_imputed_zero": missing_discount,
        "missing_rating_imputed_median": missing_rating,
        "rating_median_used": rating_median,
        "quantity_outliers": outliers.to_dict(orient="records"),
        "correlation_pairs": correlation_pairs,
        "monthly_revenue": monthly.to_dict(orient="records")
    }
    (NARRATOR / "findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
    print("\nFINDINGS JSON WRITTEN FROM COMPUTED VALUES:", NARRATOR / "findings.json")

if __name__ == "__main__": main()
