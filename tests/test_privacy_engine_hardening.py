import copy
import json
import pytest

from src.privacy_engine import PrivacyEngine
from src.tokenizer import PrivacyTokenizer


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


def test_local_mapping_is_defensive_copy():
    engine = PrivacyEngine()
    engine.sanitize(banking_state())
    mapping = engine.get_local_mapping()
    mapping.clear()
    assert engine.get_local_mapping()


def test_sensitive_url_path_is_redacted_but_query_and_fragment_removed():
    state = banking_state()
    state["url"] = "https://secure.example.local/customer/Rahul%20Sharma/profile?account=7845129034#private"
    state["elements"] = [{"element_id": "EL_001", "role": "text", "label": "Account Holder", "text": "Rahul Sharma", "visible": True, "enabled": True}]
    sanitized = PrivacyEngine().sanitize(state)
    assert "?" not in sanitized["url"]
    assert "#" not in sanitized["url"]
    assert "7845129034" not in sanitized["url"]
    assert "Rahul" not in sanitized["url"]


def test_deep_nested_sensitive_strings_are_redacted():
    state = banking_state()
    state["accessibility_snapshot"] = "Account holder Rahul Sharma, account 7845129034"
    state["visual_summary"] = ["Rahul Sharma", {"details": "Contact rahul.sharma@gmail.com"}]
    sanitized = PrivacyEngine().sanitize(state)
    payload = json.dumps(sanitized, ensure_ascii=False)
    for value in ("Rahul Sharma", "7845129034", "rahul.sharma@gmail.com"):
        assert value not in payload


def test_nested_depth_is_bounded():
    state = banking_state()
    value = "safe"
    for _ in range(10):
        value = [value]
    state["visual_summary"] = value
    with pytest.raises(ValueError, match="safe depth"):
        PrivacyEngine().sanitize(state)


def test_input_element_bound_is_enforced():
    state = banking_state()
    state["elements"] = [copy.deepcopy(state["elements"][0]) for _ in range(501)]
    with pytest.raises(ValueError, match="elements exceed safe limits"):
        PrivacyEngine().sanitize(state)


def test_input_visible_text_bound_is_enforced():
    state = banking_state()
    state["visible_text"] = "x" * 20_001
    with pytest.raises(ValueError, match="visible_text exceeds safe limits"):
        PrivacyEngine().sanitize(state)


def test_input_title_bound_is_enforced():
    state = banking_state()
    state["title"] = "x" * 301
    with pytest.raises(ValueError, match="title exceeds safe limits"):
        PrivacyEngine().sanitize(state)


def test_input_url_bound_is_enforced():
    state = banking_state()
    state["url"] = "https://example.local/" + ("x" * 2049)
    with pytest.raises(ValueError, match="url exceeds safe limits"):
        PrivacyEngine().sanitize(state)


def test_malformed_element_is_rejected_without_sensitive_error_text():
    state = banking_state()
    state["elements"] = ["Rahul Sharma"]
    with pytest.raises(ValueError) as exc:
        PrivacyEngine().sanitize(state)
    assert "Rahul Sharma" not in str(exc.value)


def test_placeholder_looking_input_cannot_access_mapping():
    tokenizer = PrivacyTokenizer()
    sanitized, modified = tokenizer.sanitize_node("[ACCOUNT_01]")
    assert modified is False
    assert sanitized == "[ACCOUNT_01]"
    assert tokenizer.local_mapping == {}


def test_redaction_count_includes_title_and_visible_text_spans():
    state = banking_state()
    engine = PrivacyEngine()
    sanitized = engine.sanitize(state)
    assert sanitized["privacy_summary"]["redaction_count"] >= 7


def test_same_category_reuses_token_across_recaptures():
    engine = PrivacyEngine()
    first = engine.sanitize(banking_state())
    second = engine.sanitize(copy.deepcopy(banking_state()))
    first_token = first["elements"][0]["text"]
    second_token = second["elements"][0]["text"]
    assert first_token == second_token == "[PERSON_01]"


def test_separate_engines_do_not_share_mappings():
    state = banking_state()
    engine_a = PrivacyEngine()
    engine_b = PrivacyEngine()
    engine_a.sanitize(state)
    assert engine_b.get_local_mapping() == {}


def test_sensitive_value_injected_after_sanitization_is_detected():
    engine = PrivacyEngine()
    raw = banking_state()
    sanitized = engine.tokenizer.sanitize_page_state(raw)
    sanitized["title"] = "Account 7845129034"
    assert engine._independent_privacy_check(raw, sanitized) is False
