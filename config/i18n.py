"""
Supported UI languages for JointX (spec: P2 NER language closure #7).

Each language is a capability record, not just a display label, because
"declared" and "actually usable for clinical content" are different
questions that the UI must never conflate:

  text_status:
    FULL         -- every UI key (nav/login/questionnaire/gait/imu/
                    functional/results/report) has a translation in
                    frontend/static/js/i18n.js
    PARTIAL      -- only the highest-traffic screens (nav/login/dashboard)
                    are translated; the rest falls back to English
    UNTRANSLATED -- declared (so it appears in the picker, honestly showing
                    "not yet available") but has no translated strings at all

  is_ner: whether this is one of the North-Eastern-Region languages the
    project's problem statement specifically targets. Tamil is retained for
    general accessibility but is NOT an NER language -- it must never be
    mistaken for NER-specific coverage in the admin UI or in any coverage
    report, hence is_ner=False and a distinct label.

CLINICAL_CRITICAL_KEYS lists every i18n key that carries clinical meaning
(risk level names, disclaimers, escalation/referral text). Even a language
marked text_status=FULL never serves a clinical-critical key unless that
language is also in CLINICALLY_VERIFIED_LANGUAGES -- see
frontend/static/js/i18n.js's t()/apply(), which fall back to English with a
visible "translation pending clinical review" marker otherwise. A language
only enters CLINICALLY_VERIFIED_LANGUAGES after a second person (not the
original translator) has reviewed those specific strings; en/hi/bn/as/ne/ta
were reviewed as part of earlier development, kha and lus's FULL text was
added in this pass without that second-person clinical review yet, so their
clinical-critical strings are deliberately NOT verified until that happens.
"""

LANGUAGE_CAPABILITIES = {
    "en": {"endonym": "English", "english_name": "English", "text_status": "FULL", "is_ner": False},
    "hi": {"endonym": "हिन्दी", "english_name": "Hindi", "text_status": "FULL", "is_ner": False},
    "bn": {"endonym": "বাংলা", "english_name": "Bengali", "text_status": "FULL", "is_ner": False},
    "as": {"endonym": "অসমীয়া", "english_name": "Assamese", "text_status": "FULL", "is_ner": True},
    "ne": {"endonym": "नेपाली", "english_name": "Nepali", "text_status": "FULL", "is_ner": True},
    "ta": {
        "endonym": "தமிழ்", "english_name": "Tamil", "text_status": "FULL",
        # Retained for accessibility (widely spoken, well-supported voice/
        # font stack) but is explicitly NOT a North-Eastern-Region language
        # -- never present this as NER coverage in admin UI or reports.
        "is_ner": False, "accessibility_only": True,
    },
    "kha": {"endonym": "Khasi", "english_name": "Khasi", "text_status": "FULL", "is_ner": True},
    "lus": {"endonym": "Mizo ṭawng", "english_name": "Mizo", "text_status": "FULL", "is_ner": True},
    "brx": {"endonym": "बड़ो", "english_name": "Bodo", "text_status": "PARTIAL", "is_ner": True},
    "mni": {"endonym": "ꯃꯤꯇꯩ ꯂꯣꯟ", "english_name": "Meitei (Manipuri)", "text_status": "PARTIAL", "is_ner": True},
    "grt": {"endonym": "A·chik", "english_name": "Garo", "text_status": "PARTIAL", "is_ner": True},
    "nag": {"endonym": "Nagamese", "english_name": "Nagamese", "text_status": "PARTIAL", "is_ner": True},
    "kok": {"endonym": "Kokborok", "english_name": "Kokborok", "text_status": "PARTIAL", "is_ner": True},
}

# Backward-compatible flat {code: display_label} map for anything that only
# needs a label (e.g. a simple <select> before the coverage-aware admin
# picker is wired in everywhere) -- prefer LANGUAGE_CAPABILITIES in new code.
SUPPORTED_LANGUAGES = {
    code: f"{cap['endonym']} ({cap['english_name']})" if cap["endonym"] != cap["english_name"] else cap["endonym"]
    for code, cap in LANGUAGE_CAPABILITIES.items()
}

DEFAULT_LANGUAGE = "en"

# Every i18n key carrying clinical meaning -- risk level names, disclaimers,
# and escalation/referral guidance. These require second-person clinical
# review per-language before being served over the English original; see
# module docstring and frontend/static/js/i18n.js.
CLINICAL_CRITICAL_KEYS = {
    "common.low", "common.moderate", "common.high",
    "footer.disclaimer",
    "results.proceed_review",
    "report.finalize_success",
}

# Languages whose CLINICAL_CRITICAL_KEYS translations have been reviewed by
# a second person (not the original translator) and are safe to serve
# instead of the English original. kha/lus's general UI text was completed
# in this pass but is deliberately NOT in this set yet -- their
# clinical-critical strings still show the "pending clinical review" badge
# until that review actually happens (see docs/MODEL_STATUS.md-adjacent
# process note: this is a people-process gate, not something code can
# self-certify).
CLINICALLY_VERIFIED_LANGUAGES = {"en", "hi", "bn", "as", "ne", "ta"}


def text_coverage_percent(lang_code: str) -> int:
    """Coarse coverage indicator for the admin Translation Coverage picker."""
    cap = LANGUAGE_CAPABILITIES.get(lang_code)
    if not cap:
        return 0
    return {"FULL": 100, "PARTIAL": 35, "UNTRANSLATED": 0}[cap["text_status"]]


def facility_default_language(facility_name: str) -> str:
    """
    Facility-level default UI language (spec: P2 #7 -- "for a Nagaland
    deployment the facility default is Nagamese, not Hindi"). This is a
    coarse name-matching placeholder; a real deployment should store this
    as an explicit admin-configured field per facility (see
    healthcare_workers.facility_name / a future facilities table) rather
    than pattern-matching on the name string. Falls back to DEFAULT_LANGUAGE.
    """
    if not facility_name:
        return DEFAULT_LANGUAGE
    name = facility_name.lower()
    if "nagaland" in name:
        return "nag"
    if "meghalaya" in name or "khasi" in name:
        return "kha"
    if "mizoram" in name:
        return "lus"
    if "assam" in name:
        return "as"
    return DEFAULT_LANGUAGE
