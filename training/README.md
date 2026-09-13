# JointX Training Pipeline

This directory is **completely separate** from the real-time inference path
(`fusion/`, `ml/predictor.py`). Nothing here runs during a live screening.

## Why no model ships with this repo

JointX does not include a pre-trained clinical model. Training a real one
requires a labelled, subject-independent dataset of gait, IMU, and
questionnaire data with clinician-confirmed OA outcomes, which is outside
the scope of this codebase. Until that exists, the app runs in
**UNVALIDATED PROTOTYPE MODE** (see `ml/models/README.md`).

## Pipeline

```
Live database (data/jointx.db)
   -> export_dataset.py       (pulls fused_features + a clinician-confirmed
                                risk_label per screening into a raw_dataset.csv;
                                real screenings only, feature values are never
                                recomputed here -- see fusion/fusion.py)
   -> preprocessing.py       (cleaning, missing-value handling)
   -> feature_engineering.py (must reuse fusion/feature_schema.py — do not
                               invent a second feature list)
   -> split.py                (SUBJECT-INDEPENDENT train/test split)
   -> train.py                (fits XGBoost using config/model_config.py params)
   -> evaluate.py              (sensitivity, specificity, precision, recall,
                                F1, ROC-AUC on the held-out subject split)
   -> export model to ml/models/ ONLY if evaluation results are acceptable
```

## Data leakage prevention

`split.py` splits by **patient/subject ID**, never by row. A patient's
screenings must appear entirely in either the train set or the test set,
never both.

## Reporting metrics

Only report metrics that `evaluate.py` actually computed from real held-out
data. Never hard-code example accuracy numbers anywhere in this codebase.

## Ground truth: where risk_label comes from

There is no dedicated "ground truth" data-entry screen. A screening's label
comes from `backend/services/review_service.py` (the healthcare-worker
Review step): either a `clinician_label` recorded by the reviewer, or an
`agrees_with_model=1` review (which trusts the model's own prediction as
confirmed correct). A review that disagrees with the model without setting
`clinician_label` has no usable label and is skipped by `export_dataset.py`.

## Running (once you have enough reviewed, real screenings)

```bash
python training/export_dataset.py --output training/datasets/raw_dataset.csv
python training/preprocessing.py --input training/datasets/raw_dataset.csv --output training/datasets/clean_dataset.csv
python training/feature_engineering.py --input training/datasets/clean_dataset.csv --output training/datasets/features.csv
python training/split.py --input training/datasets/features.csv --train-output training/datasets/train.csv --test-output training/datasets/test.csv
python training/train.py --train training/datasets/train.csv --output ml/models/jointx_xgb_model.json
python training/evaluate.py --model ml/models/jointx_xgb_model.json --test training/datasets/test.csv
```

Each script prints its own usage instructions when run without arguments.
