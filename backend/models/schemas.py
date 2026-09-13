"""
Lightweight dataclasses mirroring the SQLite tables. These are used for
type-hinting and serialization convenience in services; they are NOT an ORM.
The database/schema.sql file remains the single source of truth for storage.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Patient:
    id: Optional[int] = None
    patient_code: str = ""
    full_name: str = ""
    age: Optional[int] = None
    sex: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    village_or_area: Optional[str] = None
    contact_phone: Optional[str] = None


@dataclass
class Questionnaire:
    screening_id: int
    pain_score: int = 0
    stiffness_score: int = 0
    mobility_difficulty: int = 0
    walking_difficulty: int = 0
    stairs_difficulty: int = 0
    standing_difficulty: int = 0
    sit_to_stand_difficulty: int = 0
    previous_joint_problems: str = ""
    lifestyle_notes: str = ""


@dataclass
class RiskResult:
    risk_label: str
    risk_score: Optional[float]
    is_prototype: bool
    model_version: str
    top_features: list = field(default_factory=list)
