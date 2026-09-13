# ml/models/

Place a trained, evaluated XGBoost model file here, named to match
`JOINTX_MODEL_PATH` in your `.env` (defaults to `jointx_xgb_model.json`).

No model ships with this repository. Until a real model is trained on a
subject-independent split and evaluated (see `training/`), JointX runs in
**UNVALIDATED PROTOTYPE MODE**: predictions come from a transparent,
clearly-labelled heuristic in `ml/predictor.py`, not a trained classifier,
and the UI always shows "Demo/Prototype Output — Not Clinical Prediction".

To produce a real model:

1. Collect and label a subject-independent dataset (see `training/README.md`).
2. Run `training/train.py` to fit an XGBoost model using
   `config/model_config.py:XGBOOST_TRAIN_PARAMS` and the feature order in
   `fusion/feature_schema.py`.
3. Run `training/evaluate.py` to compute sensitivity, specificity, precision,
   recall, F1, and ROC-AUC on a held-out subject-independent test set.
4. Only if evaluation results are acceptable, export the model with
   `booster.save_model("jointx_xgb_model.json")` and place it here.
5. Never hard-code or fabricate accuracy numbers anywhere in the app —
   evaluation metrics must always come from `training/evaluate.py`'s actual
   output.
