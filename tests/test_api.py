def test_full_screening_workflow(app, logged_in_client):
    c = logged_in_client

    # Register patient
    res = c.post("/api/patients", json={"full_name": "Workflow Patient", "age": 62,
                                          "sex": "M", "height_cm": 170, "weight_kg": 80})
    patient_id = res.get_json()["data"]["id"]

    # Start screening (demo mode)
    res = c.post("/api/screenings", json={"patient_id": patient_id, "is_demo": True})
    screening_id = res.get_json()["data"]["id"]

    # Questionnaire
    res = c.post("/api/questionnaire", json={
        "screening_id": screening_id, "pain_score": 6, "stiffness_score": 5,
        "mobility_difficulty": 4, "walking_difficulty": 3, "stairs_difficulty": 5,
        "standing_difficulty": 2, "sit_to_stand_difficulty": 3,
    })
    assert res.status_code == 201

    # Gait (demo)
    res = c.post("/api/gait/analyze", json={"screening_id": screening_id, "is_demo": True})
    assert res.status_code == 200
    assert res.get_json()["data"]["data_quality_ok"] is True

    # IMU calibrate + analyze (demo)
    c.post("/api/imu/calibrate", json={})
    res = c.post("/api/imu/analyze", json={"screening_id": screening_id})
    assert res.status_code == 200

    # Fuse features
    res = c.post("/api/features/fuse", json={"screening_id": screening_id})
    assert res.status_code == 200

    # Predict (also runs SHAP)
    res = c.post("/api/predict", json={"screening_id": screening_id})
    assert res.status_code == 200
    assert res.get_json()["data"]["risk_label"] in ("LOW", "MODERATE", "HIGH")

    res = c.get(f"/api/shap/{screening_id}")
    assert res.status_code == 200

    # Review
    res = c.post("/api/review", json={"screening_id": screening_id, "notes": "Looks fine",
                                        "agrees_with_model": 1})
    assert res.status_code == 201

    # Referral
    res = c.post("/api/referrals", json={"screening_id": screening_id, "status": "PENDING"})
    assert res.status_code == 201

    # Report + finalize
    res = c.get(f"/api/reports/{screening_id}")
    assert res.status_code == 200
    assert "disclaimer" in res.get_json()["data"]

    res = c.post(f"/api/reports/{screening_id}/finalize")
    assert res.status_code == 200


def test_dashboard_summary(app, logged_in_client):
    res = logged_in_client.get("/api/screenings/dashboard/summary")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "total_patients" in data
    assert "risk_distribution" in data


def test_device_status_endpoint(app, logged_in_client):
    res = logged_in_client.get("/api/device-status")
    assert res.status_code == 200
    assert "demo_mode" in res.get_json()["data"]
