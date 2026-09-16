import json

from src.privacy_engine import PrivacyEngine


def banking_state():
    return {
        "schema_version": "1.0",
        "page_state_id": "PS_PrivacyHardening01",
        "captured_at": "2026-09-16T10:00:00Z",
        "url": "https://secure.example.local/dashboard?email=rahul.sharma@gmail.com&account=7845129034#balance",
        "title": "Rahul Sharma Account Dashboard",
        "visible_text": "Welcome Rahul Sharma | Account: 7845129034 | Balance: ₹84,250 | Contact: rahul.sharma@gmail.com",
        "elements": [
            {"element_id": "EL_001", "role": "text", "label": "Rahul Sharma", "text": "Rahul Sharma", "visible": True, "enabled": True},
            {"element_id": "EL_002", "role": "text", "label": "Account Number", "value": "7845129034", "visible": True, "enabled": True},
            {"element_id": "EL_003", "role": "text", "label": "Balance", "value": "₹84,250", "visible": True, "enabled": True},
        ],
        "accessibility_snapshot": "Account holder Rahul Sharma, account 7845129034",
        "visual_summary": "Rahul Sharma dashboard",
    }


def test_label_and_metadata_are_sanitized():
    engine = PrivacyEngine()
    sanitized = engine.sanitize(banking_state())
    payload = json.dumps(sanitized, ensure_ascii=False)

    assert "Rahul Sharma" not in payload
    assert "7845129034" not in payload
    assert "rahul.sharma@gmail.com" not in payload
    assert "₹84,250" not in payload
    assert sanitized["elements"][0]["label"].startswith("[PERSON_")


def test_sensitive_query_string_is_removed_from_url():
    engine = PrivacyEngine()
    sanitized = engine.sanitize(banking_state())
    assert "?" not in sanitized["url"]
    assert "#" not in sanitized["url"]
    assert "rahul.sharma@gmail.com" not in sanitized["url"]
    assert "7845129034" not in sanitized["url"]


def test_nested_structural_strings_are_sanitized():
    engine = PrivacyEngine()
    sanitized = engine.sanitize(banking_state())
    payload = json.dumps(sanitized, ensure_ascii=False)
    assert "Rahul Sharma" not in payload
    assert "7845129034" not in payload


def test_same_raw_value_keeps_category_specific_tokens():
    state = banking_state()
    state["elements"].append({
        "element_id": "EL_004",
        "role": "text",
        "label": "Phone",
        "value": "7845129034",
        "visible": True,
        "enabled": True,
    })
    engine = PrivacyEngine()
    sanitized = engine.sanitize(state)
    account_value = sanitized["elements"][1]["value"]
    phone_value = sanitized["elements"][3]["value"]
    assert account_value.startswith("[ACCOUNT_")
    assert phone_value.startswith("[PHONE_")
    assert account_value != phone_value


def test_independent_privacy_check_detects_unmapped_leak():
    engine = PrivacyEngine()
    raw = banking_state()
    raw["title"] = "Rahul Sharma"
    sanitized = engine.tokenizer.sanitize_page_state(raw)
    sanitized["title"] = "Rahul Sharma"
    assert engine._independent_privacy_check(raw, sanitized) is False


def test_restore_remains_local_only():
    engine = PrivacyEngine()
    sanitized = engine.sanitize(banking_state())
    token = sanitized["elements"][1]["value"]
    assert token.startswith("[ACCOUNT_")
    assert engine.restore_value(token) == "7845129034"
    assert token in sanitized["elements"][1]["value"]


def test_clear_session_removes_local_mapping():
    engine = PrivacyEngine()
    engine.sanitize(banking_state())
    assert engine.get_local_mapping()
    engine.clear_session()
    assert engine.get_local_mapping() == {}
    assert engine.get_privacy_stats()["status"] == "no_sanitization_performed"


def test_privacy_summary_reports_verification():
    engine = PrivacyEngine()
    sanitized = engine.sanitize(banking_state())
    summary = sanitized["privacy_summary"]
    assert summary["verification_passed"] is True
    assert summary["redaction_count"] > 0
    assert summary["categories"]
