"""
Role tiers for JointX (spec: role-based access). healthcare_workers.role holds
a specific job title (ASHA/ANM/CHO/PHC_STAFF/DOCTOR/ADMIN); routes and nav
visibility care only about the coarser TIER a role maps to.
"""

ROLE_TIERS = {
    "ASHA": "worker",
    "ANM": "worker",
    "CHO": "worker",
    "PHC_STAFF": "worker",
    "DOCTOR": "reviewer",
    "ADMIN": "admin",
}

TIER_LABELS = {
    "worker": "Healthcare Worker",
    "reviewer": "Doctor / Reviewer",
    "admin": "Administrator",
}


def tier_for_role(role: str) -> str:
    return ROLE_TIERS.get((role or "").upper(), "worker")


def label_for_role(role: str) -> str:
    return TIER_LABELS.get(tier_for_role(role), "Healthcare Worker")
