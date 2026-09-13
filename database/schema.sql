-- JointX SQLite schema
-- Offline-first local store. All foreign keys enforced (PRAGMA foreign_keys=ON
-- is set by database/database.py on every connection).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS healthcare_workers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'ASHA',  -- ASHA/ANM/CHO/PHC_STAFF/ADMIN
    facility_name   TEXT,
    language        TEXT NOT NULL DEFAULT 'en',  -- UI language preference (see config/roles.py callers)
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS patients (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code        TEXT NOT NULL UNIQUE,   -- human-friendly local ID
    full_name           TEXT NOT NULL,
    age                 INTEGER,
    sex                 TEXT,                   -- M/F/OTHER
    height_cm           REAL,
    weight_kg           REAL,
    village_or_area      TEXT,
    contact_phone       TEXT,
    registered_by       INTEGER REFERENCES healthcare_workers(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS screenings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id          INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    performed_by        INTEGER REFERENCES healthcare_workers(id),
    status              TEXT NOT NULL DEFAULT 'IN_PROGRESS',
        -- IN_PROGRESS / DATA_COLLECTED / PREDICTED / REVIEWED / COMPLETED / ABORTED
    is_demo             INTEGER NOT NULL DEFAULT 0,
    started_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT
);

CREATE TABLE IF NOT EXISTS questionnaire (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id                INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    pain_score                  INTEGER,       -- 0-10
    stiffness_score             INTEGER,       -- 0-10
    mobility_difficulty         INTEGER,       -- 0-10
    walking_difficulty          INTEGER,       -- 0-10
    stairs_difficulty           INTEGER,       -- 0-10
    standing_difficulty         INTEGER,       -- 0-10
    sit_to_stand_difficulty     INTEGER,       -- 0-10
    previous_joint_problems     TEXT,
    lifestyle_notes             TEXT,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gait_features (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id            INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    is_demo                 INTEGER NOT NULL DEFAULT 0,
    data_quality_ok         INTEGER NOT NULL DEFAULT 0,
    frames_used             INTEGER,
    mean_visibility         REAL,
    cadence                 REAL,
    step_time               REAL,
    stride_time             REAL,
    walking_speed           REAL,
    knee_angle_rom          REAL,
    stance_swing_ratio      REAL,
    left_right_asymmetry    REAL,
    gait_cycle_variability  REAL,
    raw_json                TEXT,   -- full extracted feature dict, for audit
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS imu_features (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id            INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    is_demo                 INTEGER NOT NULL DEFAULT 0,
    data_quality_ok         INTEGER NOT NULL DEFAULT 0,
    left_samples            INTEGER,
    right_samples           INTEGER,
    acceleration_rms        REAL,
    acceleration_variance   REAL,
    peak_acceleration       REAL,
    angular_velocity_rms    REAL,
    peak_angular_velocity   REAL,
    relative_joint_rom      REAL,
    movement_smoothness     REAL,
    movement_cycle_duration REAL,
    raw_json                TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS functional_features (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id            INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    is_demo                 INTEGER NOT NULL DEFAULT 0,
    sit_to_stand_ok         INTEGER NOT NULL DEFAULT 0,
    squat_ok                INTEGER NOT NULL DEFAULT 0,
    balance_ok              INTEGER NOT NULL DEFAULT 0,
    turn_ok                 INTEGER NOT NULL DEFAULT 0,
    sit_to_stand_time       REAL,
    squat_rom               REAL,
    balance_stability       REAL,
    turn_duration           REAL,
    raw_json                TEXT,   -- full per-task extracted feature dicts, for audit
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fused_features (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id    INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    feature_json    TEXT NOT NULL,   -- ordered dict matching fusion/feature_schema.py
    schema_version  TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS predictions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id        INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    risk_label          TEXT NOT NULL,       -- LOW / MODERATE / HIGH
    risk_score          REAL,                -- model probability, if available
    model_version       TEXT,
    is_prototype        INTEGER NOT NULL DEFAULT 1,  -- 1 = unvalidated prototype/demo model
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shap_explanations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id    INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    explanation_json TEXT NOT NULL,  -- list of {feature, value, contribution}
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS healthcare_reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id        INTEGER NOT NULL UNIQUE REFERENCES screenings(id) ON DELETE CASCADE,
    reviewed_by         INTEGER REFERENCES healthcare_workers(id),
    notes               TEXT,
    agrees_with_model   INTEGER,   -- 1/0/NULL
    clinician_label     TEXT,      -- LOW/MODERATE/HIGH, the reviewer's own ground-truth
                                    -- call for this screening (required for training data
                                    -- when disagreeing with the model; optional otherwise)
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS referrals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    screening_id    INTEGER NOT NULL REFERENCES screenings(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'NOT_REFERRED',
        -- NOT_REFERRED / REFERRAL_CREATED / PENDING / TELECONSULT_COMPLETED /
        -- CLINICAL_VISIT_COMPLETED / FOLLOW_UP_REQUIRED / CLOSED
    notes           TEXT,
    created_by      INTEGER REFERENCES healthcare_workers(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type     TEXT NOT NULL,   -- 'screening', 'patient', etc.
    entity_id       INTEGER NOT NULL,
    payload_json    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING / SYNCED / FAILED
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at       TEXT
);

CREATE TABLE IF NOT EXISTS device_status (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_type     TEXT NOT NULL,   -- CAMERA / IMU_LEFT / IMU_RIGHT / ESP32
    status          TEXT NOT NULL,   -- CONNECTED / DISCONNECTED / ERROR / SIMULATED
    detail          TEXT,
    checked_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_screenings_patient ON screenings(patient_id);
CREATE INDEX IF NOT EXISTS idx_referrals_screening ON referrals(screening_id);
CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);
