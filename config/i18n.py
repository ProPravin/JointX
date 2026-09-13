"""
Supported UI languages for JointX (English + the 11 Northeast-India
regional languages/lingua-francas most relevant to NER PHC deployments,
plus Tamil for wider accessibility). This is the single source of truth for
valid language codes; the frontend translation dictionary in
frontend/static/js/i18n.js must use the same codes.
"""

SUPPORTED_LANGUAGES = {
    "en": "English",
    "as": "অসমীয়া (Assamese)",
    "bn": "বাংলা (Bengali)",
    "brx": "बड़ो (Bodo)",
    "mni": "ꯃꯤꯇꯩ ꯂꯣꯟ (Meitei)",
    "kha": "Khasi",
    "grt": "Garo",
    "lus": "Mizo",
    "nag": "Nagamese",
    "ne": "नेपाली (Nepali)",
    "kok": "Kokborok",
    "hi": "हिन्दी (Hindi)",
    "ta": "தமிழ் (Tamil)",
}

DEFAULT_LANGUAGE = "en"
