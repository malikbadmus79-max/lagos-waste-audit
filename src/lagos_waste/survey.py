"""Cleaning of the resident survey export (questionnaire version 2, `survey/questionnaire.md`).

Input: the Google Forms CSV export at `data/raw/survey/survey_responses_raw.csv` (not
version-controlled). Output: `data/processed/survey_clean.csv`, one row per valid response,
with coded answers and derived service measures, and `data/interim/survey_exclusions.csv`,
listing excluded responses by ID and reason.

Privacy: the timestamp is reduced to a date, digits are removed from the area answer so that
house numbers cannot be kept, and the free-text comment (Q16) is not written to the output.

Usage (from the repository root):

    python -m lagos_waste.survey
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from lagos_waste.geo import LGAS
from lagos_waste.paths import DATA_INTERIM, DATA_PROCESSED, DATA_RAW

RAW_PATH = DATA_RAW / "survey" / "survey_responses_raw.csv"
CLEAN_PATH = DATA_PROCESSED / "survey_clean.csv"
EXCLUSIONS_PATH = DATA_INTERIM / "survey_exclusions.csv"
SOURCE_ID = "S17"
DUPLICATE_WINDOW = pd.Timedelta(minutes=30)

# Answer text (normalised with `norm`) -> code, per question number.
CODES: dict[int, dict[str, str]] = {
    0: {"yes": "yes", "no": "no"},
    3: {"tarred, good condition": "tarred_good", "tarred but badly damaged": "tarred_damaged",
        "untarred (sand or laterite)": "untarred", "footpath only": "footpath"},
    4: {"yes": "yes", "no": "no", "not sure": "not_sure"},
    5: {"room in a shared house (face-me-i-face-you)": "shared_room", "self-contained or mini flat": "self_contained",
        "flat with 2 or more bedrooms": "flat_2plus", "duplex or detached house": "duplex_detached", "other": "other"},
    6: {"yes": "yes", "no": "no"},
    7: {"psp or lawma truck": "psp_truck", "cart pusher": "cart_pusher", "estate or landlord arranges it": "estate_landlord",
        "household burns or buries it": "burn_bury", "household dumps it (drain, roadside, open plot)": "dump",
        "don't know": "dont_know"},
    8: {"weekly": "weekly", "every two weeks": "fortnightly", "monthly": "monthly", "no fixed schedule": "no_schedule",
        "don't know": "dont_know", "not applicable, we don't use the truck": "not_applicable"},
    9: {"0": "0", "1": "1", "2": "2", "3": "3", "4": "4", "5 or more": "5_plus", "don't know": "dont_know",
        "not applicable, we don't use the truck": "not_applicable"},
    10: {"within the last 7 days": "0_7_days", "8 to 14 days ago": "8_14_days", "15 to 30 days ago": "15_30_days",
         "more than a month ago": "over_30_days", "never collected": "never", "can't remember": "cant_remember"},
    12: {"yes, regularly": "regularly", "yes, sometimes": "sometimes", "no": "no",
         "landlord or estate pays (included in rent or service charge)": "landlord_estate", "don't know": "dont_know"},
    13: {"nothing": "nothing", "under ₦1,000": "under_1000", "₦1,000 to ₦2,999": "1000_2999",
         "₦3,000 to ₦4,999": "3000_4999", "₦5,000 to ₦9,999": "5000_9999", "₦10,000 or more": "10000_plus",
         "landlord or estate pays": "landlord_estate", "don't know": "dont_know"},
}
# Multiple-answer questions: option text -> output column.
OPTIONS: dict[int, dict[str, str]] = {
    11: {"wait for the next visit": "if_missed_wait", "call the psp or lawma": "if_missed_call",
         "pay a cart pusher": "if_missed_cart_pusher", "burn it": "if_missed_burn", "dump it": "if_missed_dump",
         "take it to a collection point": "if_missed_collection_point", "other": "if_missed_other"},
    14: {"not applicable, we pay regularly": "nonpay_not_applicable", "service is poor or irregular": "nonpay_poor_service",
         "cannot afford it": "nonpay_cannot_afford", "never received a bill": "nonpay_no_bill",
         "don't know who to pay": "nonpay_dont_know_who", "pay a cart pusher instead": "nonpay_pays_cart_pusher",
         "other": "nonpay_other"},
}
SINGLE_COLUMNS = {0: "consent", 3: "road_condition", 4: "truck_access", 5: "home_type", 6: "gated_estate",
                  7: "main_collector", 8: "truck_schedule", 9: "truck_pickups_4wk_answer", 10: "last_collected",
                  12: "pays_bill", 13: "monthly_fee"}

# Collections expected in 4 weeks under each stated schedule [A08].
EXPECTED_4WK = {"weekly": 4, "fortnightly": 2, "monthly": 1}
# Midpoints of the Q10 time bands, in days [A06]; "never" and "can't remember" have no value.
BAND_DAYS = {"0_7_days": 4.0, "8_14_days": 11.0, "15_30_days": 22.5, "over_30_days": 45.0}
GAP_BANDS = {"15_30_days", "over_30_days", "never"}

# Neighbourhood -> LGA, used only when the respondent answered "Not sure" to Q1.
AREA_TO_LGA = {
    "ikotun": "Alimosho", "igando": "Alimosho", "egbeda": "Alimosho", "idimu": "Alimosho", "ipaja": "Alimosho",
    "iyana ipaja": "Alimosho", "akowonjo": "Alimosho", "ayobo": "Alimosho", "abule egba": "Alimosho",
    "ejigbo": "Oshodi-Isolo", "isolo": "Oshodi-Isolo", "okota": "Oshodi-Isolo", "oshodi": "Oshodi-Isolo",
    "mafoluku": "Oshodi-Isolo", "ajegunle": "Ajeromi-Ifelodun", "amukoko": "Ajeromi-Ifelodun",
    "festac": "Amuwo-Odofin", "satellite town": "Amuwo-Odofin", "mile 2": "Amuwo-Odofin",
    "ikorodu": "Ikorodu", "ijede": "Ikorodu", "ogolonto": "Ikorodu", "ketu": "Kosofe", "ojota": "Kosofe",
    "ogudu": "Kosofe", "mile 12": "Kosofe", "magodo": "Kosofe", "ogba": "Ikeja", "alausa": "Ikeja",
    "allen": "Ikeja", "opebi": "Ikeja", "ojodu": "Ikeja", "yaba": "Lagos Mainland", "ebute metta": "Lagos Mainland",
    "oyingbo": "Lagos Mainland", "lekki": "Eti-Osa", "ajah": "Eti-Osa", "victoria island": "Eti-Osa",
    "ikoyi": "Eti-Osa", "sangotedo": "Eti-Osa", "obalende": "Lagos Island", "idumota": "Lagos Island",
    "surulere": "Surulere", "aguda": "Surulere", "ijesha": "Surulere", "bariga": "Shomolu", "gbagada": "Kosofe",
    "shomolu": "Shomolu", "mushin": "Mushin", "idi araba": "Mushin", "ilupeju": "Mushin", "agege": "Agege",
    "ogba ijaiye": "Ifako-Ijaiye", "ifako": "Ifako-Ijaiye", "ojo": "Ojo", "alaba": "Ojo", "iba": "Ojo",
    "apapa": "Apapa", "badagry": "Badagry", "epe": "Epe", "ibeju": "Ibeju-Lekki", "awoyaya": "Ibeju-Lekki",
}


def norm(value: object) -> str:
    """Lower-case, straighten quotes and collapse spaces, for matching answer text."""
    text = "" if value is None or (isinstance(value, float) and np.isnan(value)) else str(value)
    text = text.replace("’", "'").replace("‘", "'").replace("₦", "₦")
    return re.sub(r"\s+", " ", text).strip().lower()


def question_columns(columns: list[str]) -> dict[int, str]:
    """Map question numbers to export column headers (headers start with the question number)."""
    out = {}
    for col in columns:
        m = re.match(r"\s*(\d+)\.", str(col))
        if m:
            out[int(m.group(1))] = col
    return out


def code_single(value: object, question: int) -> str:
    """Code a single-answer response; blank stays blank, unknown text becomes `unrecognised`."""
    text = norm(value)
    if not text:
        return ""
    return CODES[question].get(text, "unrecognised")


def code_multi(value: object, question: int) -> dict[str, str]:
    """Code a multiple-answer response into yes/no columns by matching each option's text."""
    text = norm(value)
    options = OPTIONS[question]
    # Longest options first, so that an option contained in a longer one is not matched twice.
    remaining = text
    found = set()
    for option in sorted(options, key=len, reverse=True):
        if option in remaining:
            found.add(option)
            remaining = remaining.replace(option, " ")
    if not text:
        return {col: "" for col in options.values()}
    return {col: "yes" if opt in found else "no" for opt, col in options.items()}


def clean_area(value: object) -> str:
    """Area name with digits removed (no house numbers) and spacing tidied."""
    text = "" if pd.isna(value) else str(value)
    text = re.sub(r"\bno\.?\s*(?=\d)", " ", text, flags=re.IGNORECASE)  # "No 2" house-number prefix
    text = re.sub(r"\d+", " ", text)
    text = re.sub(r"[^\w\s,'\-/]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" ,-/").title()


def lga_from_area(area: str) -> str:
    """LGA for a neighbourhood name, or `unspecified` when no known name is found."""
    text = f" {norm(area)} "
    for name in sorted(AREA_TO_LGA, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", text):
            return AREA_TO_LGA[name]
    return "unspecified"


def parse_timestamps(values: pd.Series) -> pd.Series:
    """Parse Google Forms timestamps, choosing the date order that fits the whole column.

    Exports use the form owner's locale: '2026/10/03 10:15:22 AM GMT+1' (year first),
    '10/3/2026 13:11:19' (month first) or '03/10/2026 13:11:19' (day first). Slash dates are
    read month first unless some value only parses day first (a first number above 12).
    """
    text = values.astype(str).str.strip().str.replace(r"\s*(GMT|UTC)[+-]?\d*(:\d+)?\s*$", "", regex=True)
    if text.str.match(r"\d{4}[/-]").all():
        return pd.to_datetime(text, yearfirst=True, errors="coerce", format="mixed")
    month_first = _parse_with(text, "%m/%d/%Y")
    if month_first.notna().all():
        return month_first
    return _parse_with(text, "%d/%m/%Y")


def _parse_with(text: pd.Series, date_format: str) -> pd.Series:
    """Parse with a fixed date order, trying 24-hour and 12-hour times with or without seconds."""
    out = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")
    for time_format in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"):
        missing = out.isna()
        out[missing] = pd.to_datetime(text[missing], format=f"{date_format} {time_format}", errors="coerce")
    return out


def find_duplicates(answers: pd.DataFrame, times: pd.Series, window: pd.Timedelta = DUPLICATE_WINDOW) -> pd.Series:
    """True for a response identical to an earlier one submitted within `window`."""
    key = answers.fillna("").astype(str).apply(lambda r: "\x1f".join(r.map(norm)), axis=1)
    dup = pd.Series(False, index=answers.index)
    last_seen: dict[str, pd.Timestamp] = {}
    for i in times.sort_values().index:
        k, t = key[i], times[i]
        if k in last_seen and t - last_seen[k] <= window:
            dup[i] = True
        else:
            last_seen[k] = t
    return dup


def clean_survey(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean responses, exclusions) from a raw Google Forms export."""
    q = question_columns(list(raw.columns))
    missing = sorted({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15} - set(q))
    if missing:
        raise ValueError(f"Export is missing questions: {missing}")
    raw = raw.copy()
    raw["_time"] = parse_timestamps(raw["Timestamp"])
    raw = raw.sort_values("_time", kind="stable").reset_index(drop=True)
    raw["response_id"] = [f"R{i + 1:03d}" for i in range(len(raw))]

    answer_cols = [q[n] for n in sorted(q) if n != 16]
    consent = raw[q[0]].map(lambda v: code_single(v, 0))
    duplicate = find_duplicates(raw[answer_cols], raw["_time"])
    reason = np.select([consent != "yes", duplicate], ["no consent", "duplicate of an earlier response"], "")
    exclusions = pd.DataFrame({"response_id": raw["response_id"], "reason": reason})
    exclusions = exclusions[exclusions["reason"] != ""].reset_index(drop=True)
    keep = raw[reason == ""].reset_index(drop=True)

    out = pd.DataFrame({"response_id": keep["response_id"], "submitted_date": keep["_time"].dt.date.astype(str)})
    lga_answer = keep[q[1]].map(lambda v: str(v).strip() if pd.notna(v) else "")
    out["area"] = keep[q[2]].map(clean_area)
    out["lga"] = [a if a in LGAS else lga_from_area(area) for a, area in zip(lga_answer, out["area"])]
    out["lga_source"] = ["respondent" if a in LGAS else ("area" if lga != "unspecified" else "none")
                         for a, lga in zip(lga_answer, out["lga"])]
    for n, col in SINGLE_COLUMNS.items():
        if n != 0:
            out[col] = keep[q[n]].map(lambda v, n=n: code_single(v, n))
    for n in OPTIONS:
        coded = keep[q[n]].map(lambda v, n=n: code_multi(v, n)).apply(pd.Series)
        out = pd.concat([out, coded], axis=1)
    out["satisfaction"] = pd.to_numeric(keep[q[15]], errors="coerce").astype("Int64")
    out["has_comment"] = np.where(keep[q[16]].map(norm) != "", "yes", "no") if 16 in q else "no"
    return derive(out), exclusions


def derive(out: pd.DataFrame) -> pd.DataFrame:
    """Add service measures computed from the coded answers."""
    out = out.copy()
    out["truck_user"] = np.where(out["main_collector"] == "psp_truck", "yes", "no")
    pickups = out["truck_pickups_4wk_answer"].replace({"5_plus": "5"})
    out["truck_pickups_4wk"] = pd.to_numeric(pickups, errors="coerce").astype("Int64")
    out["expected_pickups_4wk"] = out["truck_schedule"].map(EXPECTED_4WK).astype("Int64")
    missed = (out["expected_pickups_4wk"] - out["truck_pickups_4wk"]).clip(lower=0)
    out["missed_pickups_4wk"] = missed.astype("Int64")
    out["days_since_collection"] = out["last_collected"].map(BAND_DAYS)
    out["gap_over_14_days"] = np.select(
        [out["last_collected"].isin(GAP_BANDS), out["last_collected"].isin({"0_7_days", "8_14_days"})], ["yes", "no"], "")
    out["source_id"] = SOURCE_ID
    return out


def main() -> None:
    """Clean the raw export and write the processed file and the exclusion log."""
    raw = pd.read_csv(RAW_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    clean, exclusions = clean_survey(raw)
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(CLEAN_PATH, index=False)
    exclusions.to_csv(EXCLUSIONS_PATH, index=False)
    unrec = int((clean == "unrecognised").sum().sum())
    print(f"Read {len(raw)} responses; kept {len(clean)}; excluded {len(exclusions)} "
          f"({exclusions['reason'].value_counts().to_dict()})")
    print(f"LGA from respondent: {(clean['lga_source'] == 'respondent').sum()}, "
          f"from area: {(clean['lga_source'] == 'area').sum()}, unassigned: {(clean['lga_source'] == 'none').sum()}")
    print(f"Unrecognised answers: {unrec}")
    print(f"Wrote {CLEAN_PATH} and {EXCLUSIONS_PATH}")


if __name__ == "__main__":
    main()
