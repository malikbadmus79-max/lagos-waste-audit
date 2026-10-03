# CLAUDE.md

Project context and working rules for Claude Code in the `lagos-waste-audit` repository.

## Project

Title: Paid but Not Served: Why Waste Collection Fails in Lagos.

Research question: where in Lagos household waste collection fails, and which explanation best fits the evidence.

| ID | Explanation | Testable prediction |
|----|-------------|---------------------|
| H1 | Resident non-payment | Areas with lower fee payment rates have lower pickup frequency |
| H2 | Too few operators | Areas with more households per PSP operator have more missed pickups |
| H3 | Poor road access | Streets with unpaved or narrow roads are skipped more often |
| H4 | Dumpsite bottleneck | Areas farther from active dumpsites and transfer stations have longer gaps between pickups |
| H5 | Inequality | Lower-income areas pay similar fees but receive worse service |

Scope: household solid waste collection in Lagos State, 2021 to 2026. Unit of analysis: the 20 constitutional LGAs, with LCDA detail where survey numbers allow. Industrial and medical waste, landfill engineering, waste-to-energy and drainage are out of scope.

Phases:

1. Official numbers audit (`notebooks/01_official_numbers.ipynb`, `data/processed/official_stats.csv`)
2. Located service failure from news complaints and a resident survey (`complaints.csv`, `survey_clean.csv`, `notebooks/02_where_it_fails.ipynb`)
3. Spatial join and hypothesis tests (`notebooks/03_why_it_fails.ipynb`)
4. Interactive map, README, policy brief, public write-up

## Repository layout

| Path | Contents |
|------|----------|
| `data/raw/` | Untouched downloads. Never edited in place. |
| `data/interim/` | Partly cleaned intermediate files |
| `data/processed/` | Analysis-ready CSVs |
| `docs/sources.md` | Source log with IDs S01, S02, ... |
| `docs/data_conflicts.md` | Log of disagreements between sources and how each is handled |
| `docs/assumptions.md` | Log of assumptions with IDs A01, A02, ... |
| `notebooks/` | Numbered analysis notebooks |
| `src/lagos_waste/` | Importable Python package with all reusable logic |
| `tests/` | pytest tests for `src/lagos_waste/` |
| `reports/figures/` | Saved charts (PNG and HTML) |
| `reports/maps/` | Saved maps (HTML) |
| `survey/` | Questionnaire, codebook and Google Apps Script form builder |
| `app/` | Streamlit application |

## Data rules

- Every figure in `data/processed/` carries a `source_id` column that matches an entry in `docs/sources.md`.
- Source log columns: ID, title, publisher, author, publication date, access date, URL, type, reliability (High, Medium, Low), notes.
- Reliability scale: High for primary official documents (budgets, gazettes, statutory reports); Medium for official statements reported by established news outlets; Low for unattributed figures, blogs and secondary aggregators.
- Where two sources report different values for the same metric and period, both values are kept and the conflict is recorded in `docs/data_conflicts.md` with its resolution.
- Assumptions are recorded in `docs/assumptions.md` and referenced by ID wherever they are used in code, notebooks or reports.
- Derived values (for example daily averages from monthly totals) state the calculation and the period length used.
- Raw files are never overwritten. Cleaning steps write new files to `data/interim/` or `data/processed/`.

## Privacy and legal rules

- No respondent names, phone numbers, email addresses or house numbers are stored in the repository. Street-level location is the finest detail kept.
- Raw survey exports stay out of version control (`data/raw/survey/` is listed in `.gitignore`).
- Interview notes are anonymised by role (for example "PSP operator, Alimosho") before they enter the repository.
- PSP operators are named only where a documented public source names them in connection with the specific claim. Otherwise results are reported at LGA or zone level.
- Full text of scraped news articles is not committed. The repository keeps URL, headline, date, outlet and extracted fields.

## Code rules

- Python 3.12 in a virtual environment at `.venv/`. Dependencies are listed in `requirements.txt`.
- Reusable logic lives in `src/lagos_waste/`. Notebooks import from the package and contain analysis and narration, not long function definitions.
- Every module in `src/lagos_waste/` has tests in `tests/`. `pytest` passes before each commit.
- Functions have type hints and short docstrings.
- File paths are built with `pathlib` relative to the repository root, so code runs on Windows and Linux.
- Web requests use a descriptive User-Agent, a delay of at least 2 seconds between requests to the same site, and respect `robots.txt`.
- API keys are read from a `.env` file through `python-dotenv`. `.env` is never committed.
- Charts are saved to `reports/figures/` with descriptive file names and include a source line naming the source IDs.

## Writing style for repository files

- Neutral, factual, third-person wording. No first or second person.
- No placeholder text, no "TODO" in committed documents, no bold lead-ins in bullet lists, no rhetorical questions.
- Facts carry a source ID in square brackets, for example [S03]. Assumptions carry an assumption ID, for example [A02].
- Numbers use thousands separators and state units and period.
