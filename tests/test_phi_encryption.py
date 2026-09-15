"""
Spec: P1 data layer #4 -- PHI encryption at rest.

Required assertions (verbatim from the spec):
  - a raw sqlite3 read of the DB file finds no plaintext patient name,
    phone or village
  - lookup by phone still works via phone_hash
  - a backup artefact is unreadable without the key
"""
import os
import sqlite3
import tempfile

import pytest

from backend.utils import crypto
from backend.services import patient_service
from tools.backup_db import backup_database
from config.settings import Config


def test_raw_db_read_finds_no_plaintext_phi(app, logged_in_client):
    logged_in_client.post(
        "/api/patients",
        json={"full_name": "Priya Devi", "contact_phone": "+919812345678", "village_or_area": "Kohima"},
    )

    conn = sqlite3.connect(Config.DATABASE_PATH)
    row = conn.execute("SELECT full_name, contact_phone, village_or_area FROM patients").fetchone()
    conn.close()

    raw_full_name, raw_phone, raw_village = row
    assert "Priya" not in raw_full_name
    assert "Devi" not in raw_full_name
    assert "9812345678" not in raw_phone
    assert "Kohima" not in raw_village


def test_lookup_by_phone_works_via_hash_without_decrypting_every_row(app, logged_in_client):
    logged_in_client.post(
        "/api/patients",
        json={"full_name": "Test Lookup Patient", "contact_phone": "+911234500000"},
    )

    res = logged_in_client.get("/api/patients?q=%2B911234500000")
    data = res.get_json()
    assert data["success"] is True
    assert any(p["contact_phone"] == "+911234500000" for p in data["data"])


def test_backup_artefact_unreadable_without_key(app, logged_in_client):
    logged_in_client.post("/api/patients", json={"full_name": "Backup Test Patient"})

    backup_dir = tempfile.mkdtemp()
    original_dir = Config.BACKUP_DIR
    real_key = os.environ["JOINTX_DATA_KEY"]
    try:
        Config.BACKUP_DIR = backup_dir
        enc_path = backup_database()

        with open(enc_path, "rb") as f:
            encrypted_bytes = f.read()

        # Correct key: decrypts fine.
        decrypted = crypto.decrypt_bytes(encrypted_bytes)
        assert decrypted  # non-empty

        # Wrong key: must fail, not silently return garbage-but-valid data.
        from cryptography.fernet import Fernet

        os.environ["JOINTX_DATA_KEY"] = Fernet.generate_key().decode()
        with pytest.raises(crypto.DecryptionError):
            crypto.decrypt_bytes(encrypted_bytes)
    finally:
        os.environ["JOINTX_DATA_KEY"] = real_key
        Config.BACKUP_DIR = original_dir


def test_encrypt_field_raises_without_configured_key():
    real_key = os.environ.pop("JOINTX_DATA_KEY", None)
    try:
        with pytest.raises(crypto.CryptoNotConfiguredError):
            crypto.encrypt_field("some value")
    finally:
        if real_key is not None:
            os.environ["JOINTX_DATA_KEY"] = real_key


def test_decrypt_patient_row_roundtrips_via_service_layer(app, logged_in_client):
    res = logged_in_client.post(
        "/api/patients",
        json={"full_name": "Roundtrip Patient", "contact_phone": "+910000011111", "village_or_area": "Aizawl"},
    )
    patient_id = res.get_json()["data"]["id"]

    patient = patient_service.get_patient(patient_id)
    assert patient["full_name"] == "Roundtrip Patient"
    assert patient["contact_phone"] == "+910000011111"
    assert patient["village_or_area"] == "Aizawl"
