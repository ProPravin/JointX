# Model Status

**No trained model ships with JointX.** Every risk prediction the app
currently produces comes from `ml/predictor.py`'s `_heuristic_score()` — a
hand-weighted sum of normalized features, not a fitted classifier. This
document states plainly what that means, what IS finished, and what has to
happen before a real model can exist.

## What "no trained model" actually means in the running app

- `ml/model_loader.py` looks for a model file at `Config.MODEL_PATH`
  (`ml/models/jointx_xgb_model.json`). That file does not exist in this
  repository and is not produced by any setup step.
- Every prediction is tagged `is_prototype: true` and `model_version:
  "prototype-heuristic-v1"` in the database and the API response.
- The heuristic's feature weights (`_HEURISTIC_WEIGHTS` in
  `ml/predictor.py`) are "roughly informed by general OA literature
  associations" — a documented, honest description of a guess, not a
  measured relationship.
- A permanent banner appears wherever a prediction is shown, stating this
  and linking here. It cannot be dismissed, because the underlying fact it
  states does not become less true when a user clicks a button.
- `GET /api/model/performance` returns an explicit "no evaluation run
  exists" response — never a zero, a placeholder number, or an empty chart
  that could be mistaken for a measured 0%.

## What IS finished and tested

The parts of the pipeline that do NOT depend on having a trained model are
complete and covered by the automated test suite:

- **Feature schema** (`fusion/feature_schema.py`) — single source of truth
  for all 32 features (25 sensor/patient/functional + 7 presence/quality
  meta-features), with correct NaN-for-missing semantics (spec: Data
  Integrity #A2).
- **Label integrity** — blinded clinician review workflow, `label_source`
  provenance tracking, `model_confirmed` rows excluded from training/test by
  default (spec: Data Integrity #A1). See `backend/services/review_service.py`
  and `training/export_dataset.py`.
- **Subject-independent train/test splitting** (`training/split.py`) —
  no patient's data crosses the train/test boundary.
- **The training pipeline itself** — `export_dataset.py` →
  `preprocessing.py` → `feature_engineering.py` → `split.py` → `train.py` →
  `evaluate.py` runs correctly end-to-end. This has been verified with
  `training/pipeline_smoke_test.py`, which generates SYNTHETIC data purely
  to prove the mechanics work (correct shapes, no crashes, sample weights
  applied, NaN handled correctly) — every artefact that script produces is
  stamped `SYNTHETIC — PIPELINE VALIDATION ONLY, NOT A PERFORMANCE CLAIM` in
  its filename, its JSON contents, and its printed summary. **A model
  trained on synthetic data is never loaded by the running app** —
  `pipeline_smoke_test.py` writes its output model file to
  `training/synthetic_only/`, a path `ml/model_loader.py` never reads from.
- **SHAP / explanation plumbing** (`ml/shap_explainer.py`) — falls back to a
  transparent heuristic contribution calculation when the `shap` package or
  a real model isn't available, same honesty rule as the prediction itself.

## What has to happen before a real model can exist

1. Real screenings captured through the actual hardware pipeline (camera +
   IMU + functional tests), at the volumes and diversity described in
   `docs/DATA_COLLECTION.md`'s target enrolment.
2. Those screenings reviewed through the blinded workflow, with a
   `label_source` of `kl_grade`, `acr_clinical`, or `clinician_impression`
   — never trained on `model_confirmed` rows (see `training/export_dataset.py`'s
   docstring for why that would be circular).
3. `training/export_dataset.py` run for real, producing a real
   `raw_dataset.csv` from actual reviewed screenings.
4. The full pipeline (`preprocessing.py` → `feature_engineering.py` →
   `split.py` → `train.py`) run on that real data.
5. `training/evaluate.py` run on the real held-out subject-independent test
   set, reporting the full confusion matrix and per-class sensitivity — never
   accuracy alone, which is actively misleading on an imbalanced screening
   population.
6. Those real evaluation numbers reviewed and judged acceptable by someone
   with the clinical/statistical authority to make that call — not
   self-certified by this codebase.
7. Only then does `ml/models/jointx_xgb_model.json` get placed at
   `Config.MODEL_PATH`, at which point `is_prototype` becomes `false` and
   `GET /api/model/performance` starts reporting the real, dated evaluation
   results instead of "no evaluation run exists."

Until all seven of those have actually happened, JointX remains, accurately
and by design, in **UNVALIDATED PROTOTYPE MODE**.
