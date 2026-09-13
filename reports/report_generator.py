"""Renders a plain-text version of a screening report for download/printing."""
from backend.services.report_service import build_report


def render_text_report(screening_id: int) -> str:
    r = build_report(screening_id)
    p = r["patient"]
    s = r["screening"]
    q = r.get("questionnaire") or {}
    gait = r.get("gait_features") or {}
    imu = r.get("imu_features") or {}
    functional = r.get("functional_features") or {}
    pred = r.get("prediction") or {}
    referrals = r.get("referrals") or []

    lines = [
        "=" * 60,
        "JOINTX — OA RISK SCREENING REPORT",
        "=" * 60,
        f"Patient: {p.get('full_name', 'N/A')} ({p.get('patient_code', 'N/A')})",
        f"Age: {p.get('age', 'N/A')}  Sex: {p.get('sex', 'N/A')}  BMI: {p.get('bmi', 'N/A')}",
        f"Screening ID: {s.get('id')}   Date: {s.get('started_at')}",
        "-" * 60,
        "QUESTIONNAIRE SUMMARY",
        f"  Pain score: {q.get('pain_score', 'N/A')}/10",
        f"  Stiffness score: {q.get('stiffness_score', 'N/A')}/10",
        f"  Mobility difficulty: {q.get('mobility_difficulty', 'N/A')}/10",
        f"  Walking difficulty: {q.get('walking_difficulty', 'N/A')}/10",
        "-" * 60,
        "GAIT FEATURES" + (" (DEMO DATA)" if gait.get("is_demo") else ""),
        f"  Data quality OK: {gait.get('data_quality_ok')}",
        f"  Cadence: {gait.get('cadence', 'N/A')}  Left-right asymmetry: {gait.get('left_right_asymmetry', 'N/A')}%",
        f"  Knee angle ROM: {gait.get('knee_angle_rom', 'N/A')}°  Stride time: {gait.get('stride_time', 'N/A')}s",
        "-" * 60,
        "IMU FEATURES" + (" (DEMO DATA)" if imu.get("is_demo") else ""),
        f"  Data quality OK: {imu.get('data_quality_ok')}",
        f"  Angular velocity RMS: {imu.get('angular_velocity_rms', 'N/A')}",
        f"  Relative joint ROM: {imu.get('relative_joint_rom', 'N/A')}°  Smoothness: {imu.get('movement_smoothness', 'N/A')}",
        "-" * 60,
        "FUNCTIONAL TESTS" + (" (DEMO DATA)" if functional.get("is_demo") else ""),
        f"  Sit-to-stand time: {functional.get('sit_to_stand_time', 'N/A')}s  Squat ROM: {functional.get('squat_rom', 'N/A')}°",
        f"  Balance stability: {functional.get('balance_stability', 'N/A')}  Turn duration: {functional.get('turn_duration', 'N/A')}s",
        "-" * 60,
        "RISK RESULT",
        f"  Risk category: {pred.get('risk_label', 'N/A')}",
        f"  Risk score: {pred.get('risk_score', 'N/A')}",
        f"  Prototype/unvalidated model: {bool(pred.get('is_prototype'))}",
    ]

    if r.get("shap_explanation"):
        lines.append("-" * 60)
        lines.append("KEY CONTRIBUTING FEATURES")
        for feat in r["shap_explanation"].get("top_features", []):
            direction = "↑" if feat["contribution"] > 0 else "↓"
            lines.append(f"  {feat['feature']:<22} {direction} contribution ({feat['contribution']})")

    if referrals:
        lines.append("-" * 60)
        lines.append("REFERRAL STATUS")
        lines.append(f"  {referrals[0]['status']} — {referrals[0].get('notes', '')}")

    lines.append("-" * 60)
    if r.get("demo_data_notice"):
        lines.append(r["demo_data_notice"])
    if r.get("prototype_notice"):
        lines.append(r["prototype_notice"])
    if r.get("further_evaluation_notice"):
        lines.append(r["further_evaluation_notice"])
    lines.append(r["disclaimer"])
    lines.append("=" * 60)

    return "\n".join(lines)
