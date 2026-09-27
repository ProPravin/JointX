"""
Honest reporting of model evaluation status (spec: P2 #8 -- "make the no
trained model position explicit and defensible").

Never returns a zero, a placeholder number, or an empty-but-shaped result
that could be mistaken for a real measured value -- either a real evaluation
run's actual results exist, or the API says plainly that none exists.
"""
import json
import os

from config.settings import Config

# Where a real evaluate.py run would write its results, if one had ever
# happened. Deliberately separate from training/synthetic_only/, which only
# ever holds pipeline-smoke-test artefacts that must never be read here.
EVALUATION_RESULTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "training", "datasets", "evaluation_results.json",
)


def get_model_performance() -> dict:
    """
    Returns either a real evaluation result (if training/evaluate.py has
    actually been run against real held-out data and its output saved to
    EVALUATION_RESULTS_PATH) or an explicit "no evaluation run exists"
    response. There is no model file at Config.MODEL_PATH in this
    repository, so in practice this always returns the latter today -- see
    docs/MODEL_STATUS.md.
    """
    model_exists = os.path.exists(Config.MODEL_PATH)

    if not model_exists:
        return {
            "evaluation_available": False,
            "reason": "No trained model exists at the configured model path. "
            "Every prediction currently comes from a transparent heuristic, "
            "not a fitted classifier. See docs/MODEL_STATUS.md.",
            "is_prototype": True,
        }

    if not os.path.exists(EVALUATION_RESULTS_PATH):
        return {
            "evaluation_available": False,
            "reason": "A model file exists but no evaluate.py run has been recorded. "
            "Refusing to report performance without an actual measured result.",
            "is_prototype": False,
        }

    with open(EVALUATION_RESULTS_PATH) as f:
        results = json.load(f)

    if results.get("synthetic"):
        # Defense in depth -- pipeline_smoke_test.py should never write here,
        # but if a synthetic-only result somehow landed at this path, refuse
        # to serve it as if it were a real measurement.
        return {
            "evaluation_available": False,
            "reason": "Only a SYNTHETIC pipeline-validation result was found at this path -- "
            "that is not a performance claim and will not be served as one. See docs/MODEL_STATUS.md.",
            "is_prototype": True,
        }

    n_gate = results.get("minimum_n_gate")
    if n_gate and not n_gate.get("passed"):
        # MINIMUM-N GATE (spec: honest evaluation for small N) -- a real
        # evaluation exists, but on too few subjects to trust. Refuse to
        # serve it to the dashboard as if it were a reliable measurement;
        # still name what exists so nobody thinks the endpoint is broken.
        return {
            "evaluation_available": False,
            "reason": f"STATISTICALLY UNRELIABLE — N TOO SMALL: {n_gate.get('reason')}. "
            "An evaluation was run, but not on enough subjects to report as a performance claim.",
            "is_prototype": False,
        }

    return {"evaluation_available": True, "is_prototype": False, **results}
