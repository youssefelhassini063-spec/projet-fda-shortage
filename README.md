# 💊 Drug Shortage Predictor

Predicts whether an active FDA-reported drug shortage is likely to be **Temporary** or **Definitive** (permanent discontinuation) — built end-to-end from raw API data to a deployed, interactive app.

**[Live demo →](#)** *https://med-shortage-forecast.streamlit.app/*

---

## Why this project

Drug shortages are reported by the FDA as they happen, but the agency doesn't say how a shortage will end. For a hospital or pharmacist, knowing early whether a shortage is likely to resolve quickly or become permanent (a supplier discontinuing a product for good) changes what they should do next — wait it out, or start looking for a substitute now.

This project builds that missing signal: a full pipeline from raw FDA data to a trained model to a usable prediction tool.

---

## What it does

- **Ingests** live shortage data from the [openFDA API](https://open.fda.gov/apis/drug/shortages/)
- **Stores** it in a normalized PostgreSQL database
- **Trains** a Random Forest model to predict shortage outcome from a drug's therapeutic category, dosage form, and manufacturer
- **Serves** it through an interactive Streamlit app with:
  - 📊 An overview dashboard (status breakdown, top categories, top dosage forms)
  - 🔮 A live prediction tool — enter a drug's characteristics, get an instant Temporary/Definitive estimate with confidence
  - 🔍 A searchable, filterable table of the full dataset

---

## How it works

```
openFDA API
     │  paginated extraction
     ▼
PostgreSQL (3 normalized tables)
     │  filtered export
     ▼
Feature engineering + one-hot encoding
     │
     ▼
Random Forest Classifier  ──► modele_random_forest.pkl
     │
     ▼
Streamlit App (deployed)
```

---

## Results

The model was evaluated on a held-out 20% test set (never seen during training):

| Metric | Value |
|---|---|
| Accuracy | 85% |
| Recall on Définitif cases | 79% |
| F1-score | 0.74 |

**Context that matters:** a model that always guessed "Temporary" would already score 73% accuracy, since that's the majority class. The real value of this model isn't the accuracy number alone — it's catching **79% of true permanent-discontinuation cases**, which is the outcome that actually matters for someone deciding whether to look for a substitute. That recall came from deliberately using `class_weight='balanced'`, trading some precision (more false alarms) for fewer missed real cases — a judgment call explained in full in [`notes.md`](notes.md).

---

## Key decisions worth knowing

- **CSV over live database for deployment** — the deployed app can't reach the local Docker/Postgres instance, so it runs off a frozen, timestamped CSV snapshot instead. This is a deliberate tradeoff, not an oversight — see the "Limitations" section below.
- **Random Forest over simpler models** — chosen specifically because the feature set (178 columns after encoding) is large relative to the training set (1283 rows); Random Forest's random sub-sampling makes it more resistant to overfitting on spurious patterns than Logistic Regression or SVM in this situation.
- **Every feature was statistically validated**, not chosen on intuition — each was cross-checked against the real outcome via grouped SQL queries before being included. Full reasoning, including rejected features and why, is in [`notes.md`](notes.md).

---

## Limitations (stated honestly)

- **Not live data.** The FDA API changes daily — this app reflects a snapshot from a specific date, shown in the app itself, not a real-time feed.
- **The target label is a simplification.** `Current` is treated as "Temporary" and `To Be Discontinued` as "Definitive" — but `Current` really just means "not resolved yet as of this snapshot," not a guarantee of a short duration. This is a modeling simplification, not an FDA-confirmed outcome.
- **Class imbalance.** Only ~27% of the training data is the Définitif class; the model's recall/precision tradeoff was tuned deliberately for this (see Results above).
- **~7 training rows per feature column** — a high enough ratio to watch for overfitting; Random Forest mitigates but doesn't eliminate this risk.

---

## Project structure

```
├── app.py                      # Streamlit app (dashboard + prediction + explorer)
├── shared_functions.py         # Shared cleaning/encoding logic (used by app + batch script)
├── batch_predict.py            # Runs the model on the full dataset for evaluation/QA
├── requirements.txt            # Python dependencies
├── create_tables.py            # Database schema setup
├── Load_data_into_postgres.py  # API extraction + load into PostgreSQL
├── export_to_csv.py            # Exports a snapshot for the app
├── prepare_ML_data.py          # Feature engineering + train/test split
├── modele_random_forest.pkl    # Trained model
├── colonnes_modele.pkl         # Column list used for encoding (ensures consistent input shape)
├── medicaments_export.csv      # Data snapshot used by the app
└── notes.md                    # Full working log of every decision made and why
```

---

## Running it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app expects `medicaments_export.csv`, `modele_random_forest.pkl`, and `colonnes_modele.pkl` in the same folder.

---

## Roadmap

- [ ] Batch-evaluate the full dataset and surface real-vs-predicted comparisons in the app
- [ ] Automated periodic retraining (e.g. via GitHub Actions) instead of a manual, one-time snapshot
- [ ] Explore resampling (SMOTE) or decision-threshold tuning as alternatives to `class_weight='balanced'`

---

## Tech stack

Python · PostgreSQL · Docker · pandas · scikit-learn · Streamlit

---

*Full decision log, including every rejected approach and why, is documented in [`notes.md`](notes.md).*
