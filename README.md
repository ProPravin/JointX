# JointX

**AI-Assisted Early Detection System for Osteoarthritis (OA) Risk Markers**

JointX is a preliminary OA **risk screening** tool for healthcare workers
(ASHA/ANM/CHO, PHC staff) in rural and remote areas. It is designed to run
**offline-first** on modest hardware (e.g. a Raspberry Pi), fusing camera-based
gait analysis, dual-IMU movement data, and a short questionnaire into a
transparent, explainable risk estimate that a healthcare worker reviews
before any referral is made.

> **JointX provides preliminary OA risk screening and does not replace
> professional clinical diagnosis.** For MODERATE/HIGH results, JointX
> displays: *"Further clinical evaluation is recommended."*

No trained, clinically-validated model ships with this repository. Out of
the box, JointX runs in **UNVALIDATED PROTOTYPE MODE** using a transparent
heuristic (see `ml/models/README.md` and `ml/predictor.py`) so the full
pipeline can be demonstrated end-to-end. It never fabricates accuracy,
sensitivity, or specificity numbers.

## Quick start (demo mode, no hardware required)

```bash
python -m venv .venv
source .venv/bin/activate            # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# .env already defaults JOINTX_DEMO_MODE=true — camera/IMU are simulated

python app.py
```

Open http://localhost:5000 — it always lands on the login page. One seeded
account per role tier is created on first run (see `config/roles.py` for
the tier mapping):

| Role tier | Username | Password |
|---|---|---|
| Admin | `admin` | `changeme123` |
| Healthcare Worker (ASHA) | `asha_field` | `AshaField@123` |
| Doctor / Reviewer | `dr_reviewer` | `DrReview@123` |

Logging in as each tier lands you on a different page (worker → register a
patient, reviewer → patient list, admin → dashboard), and role tiers are
enforced server-side (e.g. only worker/admin can start a screening; only
reviewer/admin can submit a clinical review — see `backend/utils/security.py:require_role`).

Change all three passwords (or create new accounts) before any real
deployment — `backend/services` has no self-serve account-creation UI yet;
add one via `healthcare_workers` table administration or a future admin route.

## Running tests

```bash
pip install pytest
pytest tests/
```

## Architecture

```
Patient -> Registration -> Questionnaire -> Camera gait analysis
                                          -> Dual IMU movement analysis
        -> Feature extraction -> Multimodal feature fusion
        -> XGBoost risk estimation -> SHAP explanation
        -> Risk dashboard -> Healthcare-worker review
        -> Referral / follow-up -> Local storage (SQLite)
        -> Optional sync when connectivity is available
```

- **`computer_vision/`** — OpenCV + MediaPipe Pose gait pipeline
- **`imu/`** — ESP32-C3 + dual MPU6050 communication, calibration, features
- **`fusion/`** — single source of truth for the unified feature schema
- **`ml/`** — XGBoost prediction + SHAP explanation (with prototype fallback)
- **`training/`** — fully separate offline training/evaluation pipeline
- **`backend/`** — Flask REST API, services, SQLite persistence
- **`frontend/`** — server-rendered HTML + vanilla JS UI
- **`sync/`** — store-and-forward synchronization for intermittent connectivity

See `training/README.md` for how to train and evaluate a real model, and
`ml/models/README.md` for where to place it once validated.

## Deployment notes (NER field deployment / "camp-in-a-backpack")

- Runs entirely offline; no core screening feature requires internet access.
- SQLite is the only required datastore — no external DB server.
- Designed to tolerate intermittent connectivity via the sync queue
  (`sync_queue` table, `backend/services/sync_service.py`).
- `JOINTX_DEMO_MODE` lets the app run fully on a laptop with no camera or
  IMU attached, which is useful for training healthcare workers before
  taking hardware into the field.
- No government API integrations are implemented; `JOINTX_SYNC_ENDPOINT` is
  a placeholder for wherever a given deployment needs to send data.

## Security notes

- Passwords are hashed (never stored in plaintext).
- All SQL is parameterized.
- Secrets/config come from environment variables (`.env`, gitignored).
- Logs deliberately avoid recording patient identifiers or biometric values.

## Clinical safety

JointX is a **screening aid**, not a diagnostic device. It does not and must
not claim to diagnose OA. Every risk result includes the disclaimer above,
and every prototype/demo-derived result is clearly labelled as such
throughout the UI, database, and generated reports.
