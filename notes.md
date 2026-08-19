# Project Notes — FDA Drug Shortage Prediction
 
## Project Question
Given that a drug is already in shortage, can we predict whether that shortage will be **Temporary** or **Definitive** (permanent discontinuation)?
 
*(Earlier framing — "risk of shortage" — was abandoned: the dataset only contains drugs already in shortage, with no denominator of all existing drugs, so a true risk rate isn't calculable.)*
 
---
 
## Module 1 — Data Architecture
 
**Database: PostgreSQL** — chosen over SQLite/MySQL for native JSON support (JSONB), and because it's the market standard for data engineering work.
 
**Docker** — used for isolation and reproducibility ("works on my machine" problem avoided), no heavy local install needed.
 
**Column analysis (before modeling)** — out of 1615 drugs analyzed: core fields (name, status, company, dosage form) present 100%; `openfda.*` fields ~89%; `discontinued_date`/`shortage_reason` ~27%; `pharm_class_*` fields only 6–23%. Found `generic_name` duplicated across two source locations — kept the 100%-present version.
 
**Schema: 3 normalized tables (OLTP)** — `medicaments` (core), `openfda_details`, `classifications_pharma`, linked by `medicament_id`. Chosen instead of one giant table to avoid columns that are 70–90% empty sitting next to fully-populated ones.
 
**Star schema — considered, rejected**: not justified at ~1600 rows; its performance benefits only show up at much larger scale. If aggregation needs grow later, SQL views (a "virtual data mart") on top of the current OLTP structure are the planned alternative.
 
**Security** — DB password never hardcoded; stored in `.env`, excluded from Git via `.gitignore` since the code will be public on GitHub.
 
---
 
## Module 2 — ETL Pipeline
 
**Pattern: ETL, not ELT** — chosen because the relational schema (typed columns) requires cleaning *before* insertion.
 
**Extract** — Pull-based (only option openFDA's API offers). Full extraction, not incremental (no baseline history yet, and volume too small to justify incremental complexity). Paginated in 2 calls since the API caps at 1000 results/call.
 
**Transform** — 3 operations: routing rows to the right table, flattening JSON lists into text, handling missing values (`.get()` → NULL). Done row-by-row (no need for Pandas vectorization at this volume).
 
**Load** — Manual batch run, simple append (no upsert — a known, confirmed limitation). Row-by-row insert (batch insert would only save ~3–5 seconds — not worth the added complexity here).
 
**Real bug hit and fixed** — Script accidentally run twice → data duplicated exactly 2x (3228 rows instead of 1614). Diagnosed via the exact 2.0 ratio. Fixed with `TRUNCATE TABLE ... RESTART IDENTITY CASCADE`, then a single clean re-run.
 
**Module 2 final validation** — `medicaments`: 1614 rows. `openfda_details`: 1450 rows (89.8%, matches the earlier ~89% estimate). `classifications_pharma`: 379 rows (23.5%, matches ~23% estimate). Joins across all 3 tables tested and working.
 
**Known limitations (documented, not yet fixed)**
- No upsert — re-running the script duplicates data
- No history tracking of status changes over time
- Dates stored as TEXT, not DATE — limits date-based calculations
- Flattened lists lose structure (e.g. can't cleanly search "all drugs containing Aspirin")
- No handling of deletions — if a shortage disappears from the API, it stays in the DB unchanged
**Tools**: Docker Desktop + PostgreSQL, Python venv (requests, pandas, sqlalchemy, psycopg2-binary, python-dotenv), DBeaver.
 
---
 
## Module 3 — Target Variable & Feature Selection
 
**Target** — derived from `status`: `Current` → **Temporaire** (0), `To Be Discontinued` → **Définitif** (1). `Resolved` excluded (only 25 of 1629 rows, 1.5% — too rare, and a different kind of outcome). Final balance: ~73% Temporaire / ~27% Définitif.
 
**Feature selection criteria (5 rules used)**
1. Available before the outcome is known (no data leakage)
2. Doesn't just restate the target in other words
3. Has real variance (not 95%+ one value, not near-unique per row)
4. Few missing values
5. A plausible logical link to the target
**Features validated against real data (not just intuition)**
- `dosage_form`: Injection 16.4% Définitif vs. Tablet 46.5% — ~3x spread, real signal (counter to the initial guess that "complex forms = more Définitif")
- `therapeutic_category`: Anesthesia 4.7% vs. Anti-Infective 53.9% — ~10x spread, strongest signal after company. Needed cleanup first (multi-category strings collapsed to just the first category).
- `company_name`: Baxter/Eugia 0% Définitif vs. Sandoz 71.1% — strongest spread of all three. Note: Pfizer Inc. (50%) and Hospira/Pfizer (14.9%) differ a lot despite common ownership — kept separate rather than merged.
**Features rejected**
- `generic_name` — nearly unique per row, no generalization possible
- `status` — this IS the source of the target (leakage)
- `manufacturer_name` — redundant with `company_name`, less complete (89% vs 100%)
- `route` — over-fragmented (20+ combinations per dosage form, often 1–5 cases each)
- `pharm_class_epc` — only 23% present, too sparse for a first model
- `shortage_reason` — only 27% present, needs free-text processing (out of scope for v1)
- `availability` — possible redundancy/leakage risk with status, worth revisiting later
**Final features**: `therapeutic_category` (cleaned), `dosage_form`, `company_name`
 
**Reusable method**: never validate a feature on intuition alone — always cross-check it against the real target with a grouped SQL query first.
 
---
 
## Module 3 — Data Preparation for ML
 
**Pipeline**: PostgreSQL → filtered SQL extraction (`status IN ('Current','To Be Discontinued')`) → 1604 rows → clean `therapeutic_category` (keep first category only → 78 raw combinations reduced to 23) → binary target created → one-hot encoding (178 columns, `drop_first=True`) → 80/20 stratified train/test split → 1283 train / 321 test rows.
 
**Key details**
- Filtering done in SQL, not Pandas, to avoid loading unnecessary rows
- `drop_first=True` avoids redundant columns (e.g. for 3 dosage forms, knowing 2 of them tells you the 3rd)
- `stratify=y` keeps the 73/27 split consistent in both train and test sets
- `random_state=42` makes the split reproducible across runs
- Verified: Train 73.27%/26.73%, Test 73.21%/26.79% — near-identical, stratification worked
**Honest limitations of this code**: no error handling, not modularized into functions, no automated tests, parameters hardcoded rather than in a config file. Accepted tradeoff: clarity and justified decisions prioritized over production robustness, appropriate for a first portfolio project.
 
**Watch point**: 178 columns for 1283 training rows (mostly from `company_name`'s 132 values) — a high column-to-row ratio. Not disqualifying for Random Forest, but worth remembering if results look unstable.
 
---
 
## Model Choice — Random Forest Classifier
 
**Problem type**: binary classification (0/1), so a Classifier, not a Regressor.
 
**Alternatives considered and rejected**
 
| Model | Why rejected |
|---|---|
| Logistic Regression | Riskier with the unfavorable column-to-row ratio (178 cols / 1283 rows) — uses all columns in one formula, more sensitive to spurious correlations |
| Naive Bayes | Assumes features are independent, which is false here (dosage_form and company_name are likely related) |
| SVM | Slow and unstable with 178 columns without heavy tuning |
| **Random Forest** | **Chosen** — handles a high column-to-row ratio better |
 
**Why Random Forest handles this better**: it builds many trees, each seeing only a random subset of columns and rows. Final prediction = majority vote. If one tree gets fooled by a coincidental pattern in its subsample, the others (seeing different data) usually don't repeat the same mistake. This reduces — doesn't eliminate — the overfitting risk from the high column-to-row ratio.
 
**Bonus**: `feature_importances_` lets the model's own learned importance be checked against the manual feature analysis above — good cross-validation of the feature selection process.
 
---
 
## Model Training & Evaluation — RESOLVED
 
Parameters: `n_estimators=100`, `max_depth=10`, `random_state=42`
 
**Comparison actually run (this closes the earlier open question):**
 
| Metric | Without class_weight | With class_weight='balanced' |
|---|---|---|
| Accuracy | 0.850 | 0.850 |
| Precision | 1.000 | 0.694 |
| Recall | 0.442 | 0.791 |
| F1-score | 0.613 | 0.739 |
 
**Problem found**: the unweighted model had 100% precision but only 44% recall on Définitif — it missed 48 of 86 real Définitif cases, mislabeling them as Temporaire. This happens because an unweighted model defaults to favoring the majority class.
 
**Fix applied**: `class_weight='balanced'`, which penalizes errors on the minority class more heavily. Recall improved from 44% → 79% (68/86 correctly caught), at the cost of precision dropping from 100% → 69% (more false alarms: 30 drugs wrongly flagged as Définitif).
 
**Decision: keep the `class_weight='balanced'` version.** Reasoning: for the intended use (helping hospitals/pharmacists decide whether to look for a substitute), missing a real Définitif case (false negative) is more costly than an occasional false alarm — so better recall is worth the precision tradeoff here. **This is a business judgment, not a mathematical fact** — a different context where false alarms are expensive would justify the opposite choice.
 
**Final confusion matrix (balanced version):**
 
|  | Predicted Temporaire | Predicted Définitif |
|---|---|---|
| **Actual Temporaire (235)** | 205 | 30 |
| **Actual Définitif (86)** | 18 | 68 |
 
**Feature importance** confirmed the manual analysis: top features were `therapeutic_category_Anesthesia`, `dosage_form_Injection`, `therapeutic_category_Psychiatry`, `dosage_form_Tablet` — consistent in both model versions.
 
**Honest limitations**: 85% accuracy should be read carefully — a naive "always guess Temporaire" model already gets 73.2%, so the real gain is more modest than it first looks. 30 false alarms out of 235 true Temporaire cases (12.8%). Not yet tried: SMOTE resampling, decision threshold tuning, comparing against Logistic Regression with class weighting. Column-to-row ratio (176:1283) remains a watch point for overfitting.
 
**Module 3: complete.**
 
---
 
## Module 4 — Streamlit App
 
- CSV export chosen over live Postgres connection for the deployed app (Docker DB unreachable once deployed; CSV is sufficient for ~1600 rows)
- Snapshot problem: the live FDA API changes daily (observed 1673 → 1652 → 1637 → 1631 in one week). No "true" number to chase — decision made to freeze one snapshot and state the freeze date explicitly in the app, rather than pretend the data is live
- App structure: sidebar (filters + snapshot info) + 3 tabs (Overview, Predict, Explore) instead of one long scrolling page — deliberate UI choice for scannability
- Prediction encoding: same `garder_premiere_categorie()` cleaning and `pd.get_dummies()` + `reindex()` alignment used both in the live Predict widget and in batch prediction — moved into a shared file (`shared_functions.py`) to avoid keeping 3 duplicate copies of the same logic
- Batch prediction script (`batch_predict.py`) built to run the model on the entire dataset at once, adding `predicted_status` / `prediction_confidence` / `prediction_correct` columns — a transparency/QA tool, not a new prediction feature. Comparable only for Current/To Be Discontinued rows; `Resolved` rows get a prediction but no correctness check, since the model was never trained on that class.
---
 


