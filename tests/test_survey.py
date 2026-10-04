"""Tests for lagos_waste.survey, using a synthetic export with the form's question titles."""

import pandas as pd

from lagos_waste import survey

HEADERS = [
    "Timestamp",
    "0. I am 18 or older and agree to take part in this survey.",
    "1. Which Local Government Area (LGA) do you live in?",
    "2. Which area or neighbourhood do you live in?",
    "3. Which best describes the road in front of your home?",
    "4. Can a refuse truck drive up to your gate?",
    "5. What type of home do you live in?",
    "6. Is your home inside a gated estate or close with a residents' association?",
    "7. Who mainly collects your household waste?",
    "8. How often is the PSP or LAWMA truck supposed to collect your waste?",
    "9. In the last 4 weeks, how many times did the PSP or LAWMA truck actually collect your waste?",
    "10. When was your waste last collected (by anyone)?",
    "11. When the truck does not come, what does your household usually do?",
    "12. Does your household pay a waste bill?",
    "13. Roughly how much does your household pay per month?",
    "14. If your household does not pay, or pays only sometimes, what are the main reasons?",
    "15. Overall, how satisfied are you with waste collection where you live?",
    "16. Is there anything else you would like to say about waste collection in your area?",
]
A = ["2026/10/01 9:00:00 AM GMT+1", "Yes", "Alimosho", "Ikotun 12", "Tarred but badly damaged", "Yes",
     "Self-contained or mini flat", "No", "PSP or LAWMA truck", "Weekly", "1", "15 to 30 days ago",
     "Wait for the next visit, Pay a cart pusher", "Yes, sometimes", "₦1,000 to ₦2,999",
     "Service is poor or irregular, Pay a cart pusher instead", "2", "Truck rarely comes"]
B = ["2026/10/01 9:10:00 AM GMT+1", "Yes", "Not sure", "Ajegunle", "Untarred (sand or laterite)", "No",
     "Room in a shared house (face-me-I-face-you)", "No", "Cart pusher",
     "Not applicable, we don’t use the truck", "Not applicable, we don’t use the truck",
     "Within the last 7 days", "", "No", "Nothing", "Not applicable, we pay regularly, Cannot afford it", "3", ""]
C = ["2026/10/01 9:20:00 AM GMT+1", "No"] + [""] * 16
D = ["2026/10/01 9:05:00 AM GMT+1"] + A[1:]  # A resubmitted five minutes later


def export(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=HEADERS)


def test_clean_survey_codes_and_excludes() -> None:
    """Consent refusals and quick resubmissions are excluded; answers are coded."""
    clean, excl = survey.clean_survey(export(A, B, C, D))
    assert list(clean["response_id"]) == ["R001", "R003"]
    assert dict(zip(excl["response_id"], excl["reason"])) == {"R002": "duplicate of an earlier response",
                                                             "R004": "no consent"}
    a = clean.iloc[0]
    assert a["lga"] == "Alimosho" and a["area"] == "Ikotun" and a["road_condition"] == "tarred_damaged"
    assert a["missed_pickups_4wk"] == 3 and a["gap_over_14_days"] == "yes" and a["days_since_collection"] == 22.5
    assert a["if_missed_cart_pusher"] == "yes" and a["if_missed_burn"] == "no"
    assert a["nonpay_pays_cart_pusher"] == "yes" and a["nonpay_poor_service"] == "yes"
    assert a["satisfaction"] == 2 and a["has_comment"] == "yes" and a["source_id"] == "S17"


def test_lga_from_area_when_not_sure_and_not_applicable_options() -> None:
    """'Not sure' is resolved from the area name; options containing commas are matched whole."""
    clean, _ = survey.clean_survey(export(B))
    b = clean.iloc[0]
    assert b["lga"] == "Ajeromi-Ifelodun" and b["lga_source"] == "area"
    assert b["truck_schedule"] == "not_applicable" and pd.isna(b["missed_pickups_4wk"])
    assert b["nonpay_not_applicable"] == "yes" and b["nonpay_cannot_afford"] == "yes"
    assert b["nonpay_poor_service"] == "no" and b["truck_user"] == "no"


def test_no_free_text_comment_in_output() -> None:
    """The Q16 comment is not carried into the clean file."""
    clean, _ = survey.clean_survey(export(A))
    assert "Truck rarely comes" not in clean.astype(str).to_numpy().ravel()


def test_unrecognised_answer_is_flagged() -> None:
    """Answer text outside the questionnaire is coded as unrecognised, not dropped."""
    assert survey.code_single("Sometimes tarred", 3) == "unrecognised"
    assert survey.code_single("", 3) == ""


def test_lga_from_area_prefers_longer_names() -> None:
    """'Ogba Ijaiye' maps to Ifako-Ijaiye rather than to Ogba in Ikeja."""
    assert survey.lga_from_area("Ogba Ijaiye") == "Ifako-Ijaiye"
    assert survey.lga_from_area("Ogba") == "Ikeja"
    assert survey.lga_from_area("Somewhere new") == "unspecified"


def test_parse_timestamps_month_first_and_day_first() -> None:
    """Slash dates are read month first unless a value can only be day first."""
    us = survey.parse_timestamps(pd.Series(["10/3/2026 13:11:19", "10/4/2026 7:56:24"]))
    assert list(us.dt.strftime("%Y-%m-%d")) == ["2026-10-03", "2026-10-04"]
    uk = survey.parse_timestamps(pd.Series(["03/10/2026 13:11:19", "25/10/2026 07:56:24"]))
    assert list(uk.dt.strftime("%Y-%m-%d")) == ["2026-10-03", "2026-10-25"]
    iso = survey.parse_timestamps(pd.Series(["2026/10/03 10:15:22 AM GMT+1"]))
    assert iso.dt.strftime("%Y-%m-%d %H:%M").iloc[0] == "2026-10-03 10:15"


def test_clean_area_removes_house_number_prefix() -> None:
    """'No 2' before a street name is removed with the digits."""
    assert survey.clean_area("No 2 Ogidan closes shasha Akowonjo") == "Ogidan Closes Shasha Akowonjo"
