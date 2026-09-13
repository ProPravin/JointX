from flask import Blueprint, request, jsonify

from backend.services import feature_service, prediction_service, shap_service
from backend.utils.security import login_required
from backend.utils.validators import require_fields
from backend.utils.helpers import api_success

prediction_bp = Blueprint("prediction", __name__, url_prefix="/api")


@prediction_bp.route("/features/fuse", methods=["POST"])
@login_required
def fuse_features():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    fused = feature_service.fuse_screening_features(int(data["screening_id"]))
    return jsonify(api_success(fused, "Features fused"))


@prediction_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    data = request.get_json(force=True, silent=True) or {}
    require_fields(data, ["screening_id"])
    screening_id = int(data["screening_id"])
    result = prediction_service.run_prediction(screening_id)
    # SHAP explanation is generated immediately alongside the prediction so
    # the results screen always has both available together.
    shap_service.run_shap_explanation(screening_id)
    return jsonify(api_success(result, "Prediction complete"))


@prediction_bp.route("/prediction/<int:screening_id>", methods=["GET"])
@login_required
def get_prediction(screening_id):
    result = prediction_service.get_prediction(screening_id)
    return jsonify(api_success(result))


@prediction_bp.route("/shap/<int:screening_id>", methods=["GET"])
@login_required
def get_shap(screening_id):
    result = shap_service.get_shap_explanation(screening_id)
    return jsonify(api_success(result))
