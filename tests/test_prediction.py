from ml.predictor import predict_risk
from ml.shap_explainer import explain_prediction
from fusion.feature_schema import FEATURE_NAMES


def _sample_features(pain=8, stiffness=7):
    features = {name: 0.0 for name in FEATURE_NAMES}
    features.update(
        {
            "pain_score": pain,
            "stiffness_score": stiffness,
            "mobility_score": 6,
            "left_right_asymmetry": 5,
            "age": 65,
            "bmi": 28,
        }
    )
    return features


def test_predict_risk_prototype_mode_labelled():
    result = predict_risk(_sample_features())
    assert result["risk_label"] in ("LOW", "MODERATE", "HIGH")
    assert result["is_prototype"] is True
    assert result["model_version"] == "prototype-heuristic-v1"


def test_higher_pain_increases_heuristic_risk():
    low = predict_risk(_sample_features(pain=0, stiffness=0))
    high = predict_risk(_sample_features(pain=10, stiffness=10))
    assert high["risk_score"] >= low["risk_score"]


def test_explain_prediction_returns_top_features():
    explanation = explain_prediction(_sample_features())
    assert explanation["method"] in ("heuristic", "shap")
    assert len(explanation["top_features"]) > 0
    for feat in explanation["top_features"]:
        assert "feature" in feat and "contribution" in feat
