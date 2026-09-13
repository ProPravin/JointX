"""
OA screening questionnaire capture. Deliberately does NOT compute or return
any diagnosis/risk from questionnaire answers alone -- it only stores data
for later use in multimodal fusion (see spec section 6).
"""
from database.database import get_cursor
from backend.utils.validators import require_fields, validate_range


QUESTIONNAIRE_FIELDS = [
    "pain_score",
    "stiffness_score",
    "mobility_difficulty",
    "walking_difficulty",
    "stairs_difficulty",
    "standing_difficulty",
    "sit_to_stand_difficulty",
]


def submit_questionnaire(screening_id: int, data: dict) -> dict:
    require_fields(data, ["pain_score", "stiffness_score"])
    for field in QUESTIONNAIRE_FIELDS:
        if field in data:
            validate_range(data.get(field), 0, 10, field)

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM questionnaire WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO questionnaire
               (screening_id, pain_score, stiffness_score, mobility_difficulty,
                walking_difficulty, stairs_difficulty, standing_difficulty,
                sit_to_stand_difficulty, previous_joint_problems, lifestyle_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                screening_id,
                data.get("pain_score", 0),
                data.get("stiffness_score", 0),
                data.get("mobility_difficulty", 0),
                data.get("walking_difficulty", 0),
                data.get("stairs_difficulty", 0),
                data.get("standing_difficulty", 0),
                data.get("sit_to_stand_difficulty", 0),
                data.get("previous_joint_problems", ""),
                data.get("lifestyle_notes", ""),
            ),
        )

    with get_cursor() as cur:
        cur.execute("SELECT * FROM questionnaire WHERE screening_id = ?", (screening_id,))
        return dict(cur.fetchone())
