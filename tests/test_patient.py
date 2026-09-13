def test_create_and_get_patient(app, logged_in_client):
    res = logged_in_client.post(
        "/api/patients",
        json={"full_name": "Test Patient", "age": 55, "sex": "F"},
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    patient_id = data["data"]["id"]

    res = logged_in_client.get(f"/api/patients/{patient_id}")
    assert res.status_code == 200
    assert res.get_json()["data"]["full_name"] == "Test Patient"


def test_create_patient_missing_name_fails(app, logged_in_client):
    res = logged_in_client.post("/api/patients", json={"age": 40})
    assert res.status_code == 400
    assert res.get_json()["success"] is False


def test_search_patients(app, logged_in_client):
    logged_in_client.post("/api/patients", json={"full_name": "Alice Example"})
    res = logged_in_client.get("/api/patients?q=Alice")
    data = res.get_json()
    assert data["success"] is True
    assert any(p["full_name"] == "Alice Example" for p in data["data"])


def test_patients_require_login(app, client):
    res = client.get("/api/patients")
    assert res.status_code == 401
