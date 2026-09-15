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


def test_search_patients_by_patient_code_partial_match(app, logged_in_client):
    create_res = logged_in_client.post("/api/patients", json={"full_name": "Alice Example"})
    patient_code = create_res.get_json()["data"]["patient_code"]

    # full_name/contact_phone are encrypted at rest (spec: P1 data layer #4),
    # so partial-text search against them is no longer possible -- only
    # patient_code (never encrypted) supports a LIKE-style partial match.
    res = logged_in_client.get(f"/api/patients?q={patient_code[:6]}")
    data = res.get_json()
    assert data["success"] is True
    assert any(p["patient_code"] == patient_code for p in data["data"])


def test_search_patients_by_exact_full_name(app, logged_in_client):
    logged_in_client.post("/api/patients", json={"full_name": "Alice Example"})

    # Exact match works via the deterministic full_name_hash column.
    res = logged_in_client.get("/api/patients?q=Alice Example")
    data = res.get_json()
    assert data["success"] is True
    assert any(p["full_name"] == "Alice Example" for p in data["data"])

    # A partial name no longer matches -- this is the documented trade-off
    # of encrypting full_name, not a bug.
    res = logged_in_client.get("/api/patients?q=Alice")
    data = res.get_json()
    assert not any(p["full_name"] == "Alice Example" for p in data["data"])


def test_patients_require_login(app, client):
    res = client.get("/api/patients")
    assert res.status_code == 401
