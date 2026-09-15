"""
Spec: P2 NER language closure #7.

Required assertions:
  - every declared language code has a capability record
  - no language claims FULL with missing keys (checked structurally: FULL
    languages' translation blocks in i18n.js must cover the same key set
    as the English block)
  - clinical-critical keys are verified-or-English in every language
  - Tamil is explicitly labelled non-NER / accessibility-only
"""
import re
from pathlib import Path

from config.i18n import (
    LANGUAGE_CAPABILITIES,
    CLINICAL_CRITICAL_KEYS,
    CLINICALLY_VERIFIED_LANGUAGES,
    SUPPORTED_LANGUAGES,
    text_coverage_percent,
)

I18N_JS_PATH = Path(__file__).resolve().parent.parent / "frontend" / "static" / "js" / "i18n.js"


def test_every_supported_language_has_a_capability_record():
    for code in SUPPORTED_LANGUAGES:
        assert code in LANGUAGE_CAPABILITIES, f"{code} is in SUPPORTED_LANGUAGES but missing a capability record"


def test_capability_records_have_required_fields():
    for code, cap in LANGUAGE_CAPABILITIES.items():
        assert cap["text_status"] in ("FULL", "PARTIAL", "UNTRANSLATED"), code
        assert isinstance(cap["is_ner"], bool), code
        assert cap["endonym"], code
        assert cap["english_name"], code


def test_tamil_is_explicitly_not_ner():
    ta = LANGUAGE_CAPABILITIES["ta"]
    assert ta["is_ner"] is False
    assert ta.get("accessibility_only") is True


def test_clinically_verified_languages_are_a_subset_of_declared_languages():
    assert CLINICALLY_VERIFIED_LANGUAGES.issubset(set(LANGUAGE_CAPABILITIES.keys()))


def test_clinical_critical_keys_cover_risk_labels_and_disclaimer():
    assert "common.low" in CLINICAL_CRITICAL_KEYS
    assert "common.moderate" in CLINICAL_CRITICAL_KEYS
    assert "common.high" in CLINICAL_CRITICAL_KEYS
    assert "footer.disclaimer" in CLINICAL_CRITICAL_KEYS


def test_coverage_percent_matches_text_status():
    assert text_coverage_percent("en") == 100
    assert text_coverage_percent("kha") == 100
    assert text_coverage_percent("lus") == 100
    assert text_coverage_percent("brx") < 100
    assert text_coverage_percent("nonexistent-code") == 0


def _extract_translation_block(js_source: str, lang_code: str) -> str:
    """
    Pulls the T.<lang> = { ... }; block (or the inline `<lang>: { ... },`
    block inside the T object literal) out of i18n.js's source text, for a
    structural completeness check without needing a JS runtime.
    """
    # en/hi/bn/as/ne/ta are defined as `<code>: { ... },` inside the T object
    # literal; kha/lus/brx/... are defined as standalone `T.<code> = { ... };`
    inline_match = re.search(rf"\n\s*{re.escape(lang_code)}:\s*\{{(.*?)\n\s*\}},\n", js_source, re.DOTALL)
    if inline_match:
        return inline_match.group(1)
    standalone_match = re.search(rf"T\.{re.escape(lang_code)}\s*=\s*\{{(.*?)\n\s*\}};", js_source, re.DOTALL)
    if standalone_match:
        return standalone_match.group(1)
    raise AssertionError(f"Could not find a translation block for '{lang_code}' in i18n.js")


def test_full_status_languages_cover_the_same_keys_as_english():
    js_source = I18N_JS_PATH.read_text(encoding="utf-8")
    key_pattern = re.compile(r"'([a-z_]+\.[a-z_0-9]+)':")

    english_block = _extract_translation_block(js_source, "en")
    english_keys = set(key_pattern.findall(english_block))
    assert len(english_keys) > 50, "sanity check: the English block should have the full ~65-key UI vocabulary"

    for code, cap in LANGUAGE_CAPABILITIES.items():
        if cap["text_status"] != "FULL":
            continue
        block = _extract_translation_block(js_source, code)
        lang_keys = set(key_pattern.findall(block))
        missing = english_keys - lang_keys
        assert not missing, (
            f"Language '{code}' is declared text_status=FULL but is missing keys: {sorted(missing)}"
        )


def test_kha_and_lus_are_full_ner_languages():
    """The spec's specific deliverable: at least two of kha/lus/nag/grt at FULL."""
    assert LANGUAGE_CAPABILITIES["kha"]["text_status"] == "FULL"
    assert LANGUAGE_CAPABILITIES["kha"]["is_ner"] is True
    assert LANGUAGE_CAPABILITIES["lus"]["text_status"] == "FULL"
    assert LANGUAGE_CAPABILITIES["lus"]["is_ner"] is True
