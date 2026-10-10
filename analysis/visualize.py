"""Regenerate the two required charts from clean_and_eda.py outputs."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "visualizations"
OUT.mkdir(exist_ok=True)
payment = pd.read_csv(DATA / "return_rate_by_payment.csv").sort_values("return_rate_pct", ascending=False)
fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(payment["payment_method"], payment["return_rate_pct"])
ax.set_ylabel("Return rate (%)")
ax.set_xlabel("Payment method")
ax.set_title("COD Returns at 44.4% — 3x Card")
ax.set_ylim(0, max(payment["return_rate_pct"])*1.18)
for bar, val in zip(bars, payment["return_rate_pct"]):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.6, f"{val:.1f}%", ha="center", va="bottom")
fig.tight_layout(); fig.savefig(OUT / "return_rate_by_payment.png", dpi=160); plt.close(fig)
monthly = pd.read_csv(DATA / "monthly_revenue.csv")
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(monthly["month"], monthly["revenue_excluding_outliers"], marker="o")
ax.set_xlabel("Month")
ax.set_ylabel("Revenue after discount (INR)")
ax.set_title("Outlier-Corrected Monthly Revenue — Peak: March 2026")
ax.tick_params(axis="x", rotation=30)
fig.tight_layout(); fig.savefig(OUT / "monthly_revenue_trend.png", dpi=160); plt.close(fig)
print("Saved visualizations/return_rate_by_payment.png and visualizations/monthly_revenue_trend.png")
