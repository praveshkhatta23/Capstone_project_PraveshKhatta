"""Generate a three-part SCR business narrative from computed findings.

Set GEMINI_API_KEY to use Gemini; without a key, the deterministic offline
narrative is used. Run after analysis/clean_and_eda.py.
"""
from pathlib import Path
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
FINDINGS_PATH = ROOT / "narrator" / "findings.json"
OUTPUT_PATH = ROOT / "narrator" / "sample_output.txt"

SYSTEM_INSTRUCTION = """You are a senior data analyst writing for Mamaearth's regional ops and finance heads.
Write exactly three labeled sections: Situation, Complication, Resolution (SCR).
Every number in the output must come from the supplied findings and appear with the same value; do not invent statistics, estimates, or causal explanations. Distinguish observed associations from causation. Write clearly and concisely for business stakeholders."""


def generate_scr_narrative_offline(findings: dict) -> dict:
    """Fully deterministic, keyless SCR narrative built directly from findings."""
    try:
        raw = findings["raw_total_revenue_inr"]
        clean = findings["cleaned_total_revenue_inr"]
        delta = findings["duplicate_reconciliation_delta_inr"]
        rates = findings["return_rate_by_payment"]
        segment = findings["highest_risk_segment"]
        peak = findings["true_peak_month"]
        inflated = findings["outlier_inflated_month"]
        narrative = f"""Situation
The raw SQL layer reports revenue of ₹{raw:,.2f}. The independent pandas pipeline removes five duplicate submissions and calculates cleaned revenue of ₹{clean:,.2f} across 175 orders. This gives stakeholders a reproducible baseline for returns and revenue monitoring.

Complication
COD has a return rate of {rates['COD']:.1f}%, compared with {rates['CARD']:.1f}% for CARD and {rates['UPI']:.1f}% for UPI. The highest-risk segment is COD in Tier-{segment['city_tier']} cities, where the return rate is {segment['return_rate_pct']:.1f}%. The ₹{delta:,.2f} difference between raw and cleaned revenue is exactly the combined value of the five duplicate rows; it is not caused by imputing missing discounts or ratings. January's apparent revenue of ₹{inflated['apparent_revenue_inr']:,.2f} is inflated by two unusually large-quantity orders.

Resolution
Prioritize a review of COD orders in Tier-{segment['city_tier']} cities and investigate return reasons before making policy changes; these patterns are descriptive and do not prove that COD causes returns. Use the outlier-corrected series for trend decisions: the true peak is {peak['month']} at ₹{peak['revenue_inr']:,.2f}, while January's corrected revenue is ₹{inflated['corrected_revenue_inr']:,.2f}. Continue flagging, not deleting, quantity outliers and reconcile revenue metrics with Finance before interpreting them as margin impact."""
        return {"status": "success", "narrative": narrative, "tokens": 0}
    except Exception as err:
        return {"status": "error", "narrative": None, "message": str(err)}


def generate_scr_narrative(findings: dict) -> dict:
    """Use Gemini when configured, returning a structured result in all cases."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"status": "error", "narrative": None, "message": "GEMINI_API_KEY is not set"}
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))
        # Temperature zero makes this factual business report more reproducible.
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents="Write an SCR narrative using only this findings dictionary. Build the narrative from these supplied values:\n" + json.dumps(findings, ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.0,
                max_output_tokens=2048,
            ),
        )
        if not response.text or not response.text.strip():
            return {"status": "error", "narrative": None, "message": "Gemini returned an empty response"}
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", None) if usage else None
        return {"status": "success", "narrative": response.text.strip(), "tokens": tokens}
    except Exception as err:
        return {"status": "error", "narrative": None, "message": str(err)}


def check_numeric_accuracy(narrative: str) -> dict:
    """Print pass/fail for each of the five required numeric facts."""
    normalized = narrative.replace(",", "")
    checks = {
        "cleaned revenue 97358.30": "97358.30" in normalized or "97358.3" in normalized,
        "COD return rate 44.4": "44.4" in normalized,
        "COD + Tier-2 return rate 54.5": "54.5" in normalized,
        "duplicate delta 2501.90": "2501.90" in normalized or "2501.9" in normalized,
        "March peak revenue 20318.90": bool(re.search(r"March.{0,80}20318\.9|20318\.9.{0,80}March|2026-03.{0,80}20318\.9|20318\.9.{0,80}2026-03", normalized, re.I)),
    }
    for label, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} — {label}")
    return {"checks": checks, "all_pass": all(checks.values())}


def main():
    if not FINDINGS_PATH.exists():
        raise FileNotFoundError("Run python analysis/clean_and_eda.py first to generate findings.json.")
    findings = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    result = generate_scr_narrative(findings)
    mode = "Gemini"
    if result["status"] == "error":
        print("Gemini unavailable; using offline fallback:", result["message"])
        result = generate_scr_narrative_offline(findings)
        mode = "offline fallback"
    if result["status"] != "success":
        raise RuntimeError(result.get("message", "Narrative generation failed"))
    accuracy = check_numeric_accuracy(result["narrative"])
    if not accuracy["all_pass"] and mode == "Gemini":
        print("Gemini output failed numeric validation; using offline fallback.")
        result = generate_scr_narrative_offline(findings)
        accuracy = check_numeric_accuracy(result["narrative"])
        mode = "offline fallback"
    if not accuracy["all_pass"]:
        raise AssertionError("Narrative failed one or more required numeric checks.")
    output = f"MODE: {mode}\nSTATUS: {result['status']}\n\n{result['narrative']}\n\nNUMERIC ACCURACY CHECK\n" + json.dumps(accuracy, indent=2)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print("Narrative mode:", mode)
    print("Wrote:", OUTPUT_PATH)

if __name__ == "__main__":
    main()
