"""Operator coverage and population by LGA (hypothesis H2).

Inputs:
- LAWMA Domestic and Commercial PSP Directory, January 2024 [S18], at
  `data/raw/psp/Domestic-and-Commercial-PSP-Operators.pdf` (not version-controlled because it
  lists operator telephone numbers).
- NPC 2006 census population by LGA [S19], `data/raw/population/npc_2006_census_by_lga.csv`.
- Lagos Bureau of Statistics, Abstract of Local Government Statistics 2020, Table 1.2 [S20], at
  `data/raw/stats/LGA-Statistics-ver-2020.pdf` (not version-controlled because of its size).

Output: `data/processed/coverage_by_lga.csv`, one row per LGA. Operator names are used only to
count distinct operators and are never written out.

Usage (from the repository root):

    python -m lagos_waste.coverage
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from lagos_waste.geo import LGAS
from lagos_waste.paths import DATA_PROCESSED, DATA_RAW

PSP_PDF = DATA_RAW / "psp" / "Domestic-and-Commercial-PSP-Operators.pdf"
NPC_CSV = DATA_RAW / "population" / "npc_2006_census_by_lga.csv"
STATE_PDF = DATA_RAW / "stats" / "LGA-Statistics-ver-2020.pdf"
COVERAGE_PATH = DATA_PROCESSED / "coverage_by_lga.csv"

# Areas named in the PSP directory (LGAs and LCDAs) -> constitutional LGA [A10].
AREA_TO_LGA = {
    "AGBADO OKE ODO": "Alimosho", "AGBOYI KETU": "Kosofe", "AGEGE": "Agege", "AJEROMI": "Ajeromi-Ifelodun",
    "ALIMOSHO": "Alimosho", "AMUWO ODOFIN": "Amuwo-Odofin", "APAPA": "Apapa", "APAPA IGANMU": "Apapa",
    "AYOBO/IPAJA": "Alimosho", "BADAGRY CENTRAL": "Badagry", "BADAGRY WEST": "Badagry", "BARIGA": "Shomolu",
    "COKER AGUDA": "Surulere", "EGBE IDIMU": "Alimosho", "EJIGBO": "Oshodi-Isolo", "EPE": "Epe", "EREDO": "Epe",
    "ETI OSA": "Eti-Osa", "ETI OSA EAST": "Eti-Osa", "IBA": "Ojo", "IBEJU-LEKKI": "Ibeju-Lekki",
    "IFAKO-IJAIYE": "Ifako-Ijaiye", "IFELODUN": "Ajeromi-Ifelodun", "IGANDO-IKOTUN": "Alimosho",
    "IGBOGBO BAIYEKU": "Ikorodu", "IJEDE": "Ikorodu", "IKEJA": "Ikeja", "IKORODU CENTRAL": "Ikorodu",
    "IKORODU NORTH": "Ikorodu", "IKORODU WEST": "Ikorodu", "IKOSI EJIRIN": "Epe", "IKOSI-ISHERI": "Kosofe",
    "IKOYI-OBALENDE": "Eti-Osa", "IMOTA": "Ikorodu", "IRU/VI": "Eti-Osa", "ISOLO": "Oshodi-Isolo",
    "ITIRE-IKATE": "Surulere", "KOSOFE": "Kosofe", "LAGOS ISLAND EAST": "Lagos Island",
    "LAGOS MAINLAND": "Lagos Mainland", "LEKKI LCDA": "Ibeju-Lekki", "MOSAN OKUNOLA": "Alimosho",
    "MUSHIN AJINA": "Mushin", "ODIOLOWO/OJUWOYE": "Mushin", "OJO": "Ojo", "OJODU": "Ikeja",
    "OJOKORO": "Ifako-Ijaiye", "OLORUNDA": "Badagry", "ONIGBONGBO": "Ikeja", "ORIADE": "Amuwo-Odofin",
    "ORILE AGEGE": "Agege", "OSHODI ISOLO": "Oshodi-Isolo", "OTO AWORI": "Ojo", "SHOMOLU": "Shomolu",
    "SURULERE": "Surulere", "YABA": "Lagos Mainland",
}
# Table 1.2 spelling -> project spelling.
STATE_NAMES = {
    "AGEGE": "Agege", "AJEROMI/IFELODUN": "Ajeromi-Ifelodun", "ALIMOSHO": "Alimosho", "AMUWO/ODOFIN": "Amuwo-Odofin",
    "APAPA": "Apapa", "BADAGRY": "Badagry", "EPE": "Epe", "ETI-OSA": "Eti-Osa", "IBEJU-LEKKI": "Ibeju-Lekki",
    "IFAKO/IJAIYE": "Ifako-Ijaiye", "IKEJA": "Ikeja", "IKORODU": "Ikorodu", "KOSOFE": "Kosofe",
    "LAGOS/ISLAND": "Lagos Island", "LAGOS/MAINLAND": "Lagos Mainland", "MUSHIN": "Mushin", "OJO": "Ojo",
    "OSHODI/ISOLO": "Oshodi-Isolo", "SHOMOLU": "Shomolu", "SURULERE": "Surulere",
}


def _clean(cell: object) -> str:
    """Collapse whitespace in a PDF table cell."""
    return re.sub(r"\s+", " ", str(cell or "")).strip()


def directory_rows(tables: list[list[list[object]]]) -> pd.DataFrame:
    """Rows of the PSP directory (area, operator, ward) from extracted PDF tables.

    Data rows start with a serial number in the first cell; headers and blank rows are skipped.
    """
    rows = []
    for table in tables:
        for r in table:
            if r and re.fullmatch(r"\d+", _clean(r[0])) and _clean(r[1]):
                rows.append({"area": _clean(r[1]).upper(), "operator": _clean(r[2]).upper(), "ward": _clean(r[4])})
    return pd.DataFrame(rows, columns=["area", "operator", "ward"])


def read_directory(path: Path = PSP_PDF) -> pd.DataFrame:
    """Extract all directory rows from the PSP directory PDF."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        tables = [t for page in pdf.pages for t in page.extract_tables()]
    return directory_rows(tables)


def operators_by_lga(rows: pd.DataFrame) -> pd.DataFrame:
    """Distinct operators, ward slots and directory areas per LGA; unknown areas raise an error."""
    unknown = sorted(set(rows["area"]) - set(AREA_TO_LGA))
    if unknown:
        raise ValueError(f"Directory areas without an LGA mapping: {unknown}")
    rows = rows.assign(lga=rows["area"].map(AREA_TO_LGA))
    out = rows.groupby("lga").agg(psp_operators=("operator", "nunique"), psp_ward_slots=("ward", "size"),
                                  directory_areas=("area", "nunique"))
    return out.reindex(LGAS, fill_value=0).rename_axis("lga").reset_index()


def state_population(text: str) -> pd.DataFrame:
    """2006 population by LGA from the text of Table 1.2 of the Lagos abstract [S20]."""
    rows = []
    for name, lga in STATE_NAMES.items():
        m = re.search(rf"^{re.escape(name)}\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$", text, flags=re.MULTILINE)
        if not m:
            raise ValueError(f"{name} not found in Table 1.2 text")
        rows.append({"lga": lga, "population_2006_state": int(m.group(3).replace(",", ""))})
    return pd.DataFrame(rows)


def read_state_population(path: Path = STATE_PDF, page: int = 10) -> pd.DataFrame:
    """Read Table 1.2 (printed page 2, PDF page 10) of the Lagos abstract."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return state_population(pdf.pages[page - 1].extract_text())


def build_coverage(operators: pd.DataFrame, npc: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    """Join operator counts and both population series; add residents per operator and per ward slot."""
    out = operators.merge(npc.rename(columns={"population_2006": "population_2006_npc"}), on="lga", how="left")
    out = out.merge(state, on="lga", how="left")
    for pop in ["npc", "state"]:
        col = f"population_2006_{pop}"
        out[f"residents_per_operator_{pop}"] = (out[col] / out["psp_operators"].where(out["psp_operators"] > 0)).round(0)
        out[f"residents_per_slot_{pop}"] = (out[col] / out["psp_ward_slots"].where(out["psp_ward_slots"] > 0)).round(0)
    out["source_id"] = "S18;S19;S20"
    return out


def main() -> None:
    """Build coverage_by_lga.csv and print a short check."""
    rows = read_directory()
    operators = operators_by_lga(rows)
    npc = pd.read_csv(NPC_CSV)
    state = read_state_population()
    out = build_coverage(operators, npc, state)
    COVERAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(COVERAGE_PATH, index=False)
    print(f"Directory rows: {len(rows)}; distinct operators: {rows['operator'].nunique()}; "
          f"areas: {rows['area'].nunique()}")
    print(f"Population totals: NPC {npc['population_2006'].sum():,}; state {state['population_2006_state'].sum():,}")
    print(f"Wrote {COVERAGE_PATH}")


if __name__ == "__main__":
    main()
