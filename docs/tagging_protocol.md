# Tagging protocol for news articles

Protocol for tagging the articles listed in `data/interim/news_index.csv`. Article text is read from `data/raw/news/text/<article_id>.txt` (not version-controlled). Tags are written to `data/interim/news_tags.csv`, one row per article, and validated with `python -m lagos_waste.tagging validate`.

Tagging is carried out with Claude Code in batches of 25 articles, following this protocol exactly. Only one tagging session runs at a time, because two sessions appending to the same file can tag the same batch twice. A random sample of 50 tagged articles is then checked by hand against the article text, and agreement is reported per field (`python -m lagos_waste.tagging sample` and `python -m lagos_waste.tagging accuracy`).

## Output columns

| Column | Content | Allowed values |
|--------|---------|----------------|
| article_id | ID from `news_index.csv` | Must match the index |
| relevant | Whether the article reports on household or street waste collection or disposal in Lagos State | `yes`, `no` |
| article_type | Main character of the article | `service_failure_report`, `official_statement`, `enforcement`, `policy_or_investment`, `opinion`, `other` |
| problem_types | Problems described as occurring, separated by `;` | `missed_collection`, `waste_pileup`, `illegal_dumping`, `blocked_drains`, `road_access`, `dumpsite_access`, `fees_or_billing`, `operator_capacity`, `market_waste`, `other`, `none` |
| lgas | LGAs where a described problem or event is located, separated by `;` | The 20 LGA names listed below, `Lagos-wide`, or `unspecified` |
| place_names | Neighbourhoods, markets, roads or landmarks named in connection with a problem, separated by `;` | Free text; no house numbers and no company names |
| blamed | Actors the article holds responsible for a problem, separated by `;` | `residents`, `cart_pushers`, `psp_operators`, `lawma`, `state_government`, `local_government`, `traders`, `none_stated`, `other` |
| blame_source | Who assigns the blame | `official`, `resident`, `journalist`, `expert`, `mixed`, `none` |
| psp_named | Whether the article names a specific PSP company in connection with a problem | `yes`, `no` |
| event_month | Month in which the described problem or event occurred, if stated or clearly implied | `YYYY-MM`, or blank when not determinable |
| evidence | Short paraphrase (at most 25 words) of the passage supporting `problem_types` and `lgas` | Free text; paraphrase, not a quotation |
| tagger | Who produced the row | `claude-code` for model tagging |
| tagged_on | Date the row was produced | `YYYY-MM-DD` |

## Rules

1. Read the full article text before tagging. Do not tag from the headline alone. When the saved text is only an opening sentence, a paywall notice or fewer than about 100 words of article content, set `relevant` to `no` with the default values and write "Text incomplete (paywall or extraction failure)" in `evidence`.
2. Set `relevant` to `no` for articles where waste collection in Lagos is not the subject, for example food waste campaigns, waste-to-energy investment without reference to collection, or articles about other states. Two qualifications apply. An article on another subject is relevant when it contains a specific report, tied to a named place in Lagos, of household collection failing (missed collection or uncollected refuse); only that report is tagged. Street sweeping, sweepers' pay or working conditions and street-cleaning programmes are not household collection, and such articles are not relevant unless they also report collection failure. For `relevant = no`, set `article_type` to `other`, `problem_types` to `none`, `lgas` to `unspecified`, `blamed` to `none_stated`, `blame_source` to `none` and `psp_named` to `no`.
3. Record a problem in `problem_types` only when the article describes it as happening, not when it is mentioned as a risk or a policy goal.
4. `waste_pileup` covers heaps of uncollected refuse on streets, roads, markets or neighbourhoods. `missed_collection` is used when the article states that scheduled collection did not take place. Both may apply.
5. `dumpsite_access` covers queues, flooding, closures, road conditions or dumpsites at or beyond capacity that delay or limit disposal at Olusosun, Solous, Epe or transfer loading stations.
6. `operator_capacity` covers constraints on collection operators: truck shortages, breakdowns, fuel or diesel costs, and financial strain on PSP operators.
7. `road_access` covers collection trucks unable to reach streets or neighbourhoods because roads are narrow, unpaved, flooded, broken or blocked. It is the news evidence for hypothesis H3.
8. `other` is used only for problems outside every listed type, such as health nuisance at a dumpsite with no effect on collection. Each use of `other` is explained in `evidence`.
9. Assign `lgas` from named places. Map well-known places to their LGA (for example Ikotun and Igando to Alimosho; Oyingbo to Lagos Mainland; Lekki Phase 1 and Ajah to Eti-Osa; Ojota and Ketu to Kosofe; Olusosun to Ikeja). When a place cannot be placed with confidence, add it to `place_names` and use `unspecified` for that place. Use `Lagos-wide` only when the article explicitly describes the state as a whole.
10. Record blame only when the article attributes responsibility. An enforcement report in which LAWMA arrests residents for dumping records `residents` with `blame_source = official`. Informal waste collectors (cart pushers, wheelbarrow operators) are recorded as `cart_pushers`, not `other`.
11. Never write a PSP company name in any column. Use `psp_named = yes` instead; names are handled separately under the project's rule on naming operators.
12. `evidence` is a paraphrase in neutral language, not copied text.
13. When unsure between two values, choose the more conservative one (`unspecified`, `none_stated`, `other`) and explain in `evidence`.

## Duplicate articles

Some outlets publish the same article twice under different IDs, sometimes with an added paragraph. Each copy is tagged as a separate row. `python -m lagos_waste.tagging build` treats two articles as one when they share a normalised title and were published within seven days of each other, or when they were published within two days of each other and at least 80% of the five-word sequences in the shorter text also appear in the longer text: the earliest ID is kept, and the values of `problem_types`, `lgas`, `place_names` and `blamed` are combined across the copies. `python -m lagos_waste.tagging duplicates` lists the groups found.

## Use in analysis

Counts of articles by LGA reflect where events were reported, which includes enforcement campaigns as well as service failure. `complaints.csv` therefore carries `is_service_failure`, set to `yes` when `article_type` is `service_failure_report` or `problem_types` includes `missed_collection`. Maps of service failure use only rows with `is_service_failure = yes`; enforcement and official statements are analysed separately.

## LGA names

Agege; Ajeromi-Ifelodun; Alimosho; Amuwo-Odofin; Apapa; Badagry; Epe; Eti-Osa; Ibeju-Lekki; Ifako-Ijaiye; Ikeja; Ikorodu; Kosofe; Lagos Island; Lagos Mainland; Mushin; Ojo; Oshodi-Isolo; Shomolu; Surulere.

## Hand-check procedure

1. `python -m lagos_waste.tagging sample` writes `data/interim/handcheck_sample.csv` with 50 randomly selected tagged articles (fixed seed 2026), the model tags, and empty `check_*` columns.
2. For each row, the article is read in full and each `check_*` column is filled with `ok` when the model value is correct, or with the corrected value.
3. `python -m lagos_waste.tagging accuracy` reports agreement per field. Agreement for `relevant`, `problem_types`, `lgas` and `blamed` is reported in the methods section of the brief.
