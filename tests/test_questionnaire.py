def _make_screening(client):
    p = client.post("/api/patients", json={"full_name": "Q Patient"}).get_json()
    patient_id = p["data"]["id"]
    s = client.post("/api/screenings", json={"patient_id": patient_id}).get_json()
    return s["data"]["id"]


def test_submit_questionnaire(app, logged_in_client):
    screening_id = _make_screening(logged_in_client)
    res = logged_in_client.post(
        "/api/questionnaire",
        json={
            "screening_id": screening_id,
            "pain_score": 6,
            "stiffness_score": 4,
            "mobility_difficulty": 3,
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["data"]["pain_score"] == 6


def test_questionnaire_rejects_out_of_range(app, logged_in_client):
    screening_id = _make_screening(logged_in_client)
    res = logged_in_client.post(
        "/api/questionnaire",
        json={"screening_id": screening_id, "pain_score": 99, "stiffness_score": 2},
    )
    assert res.status_code == 400
