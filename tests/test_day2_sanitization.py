import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from src.tokenizer import PrivacyTokenizer, sanitize_page_state


BANKING_PAGE_STATE = {
    "schema_version": "1.0",
    "page_state_id": "PS_Day2Demo01",
    "captured_at": "2026-09-15T07:00:00Z",
    "url": "https://example.local/banking",
    "title": "SecureBank Dashboard",
    "visible_text": (
        "SecureBank Dashboard Latest transaction: Amazon — ₹2,340 "
        "Contact: rahul.sharma@gmail.com"
    ),
    "elements": [
        {
            "element_id": "EL_001",
            "role": "heading",
            "text": "SecureBank Dashboard",
            "visible": True,
            "enabled": True,
        },
        {
            "element_id": "EL_002",
            "role": "text",
            "label": "Name",
            "text": "Rahul Sharma",
            "visible": True,
            "enabled": True,
        },
        {
            "element_id": "EL_003",
            "role": "text",
            "label": "Account Number",
            "value": "7845129034",
            "visible": True,
            "enabled": True,
        },
        {
            "element_id": "EL_004",
            "role": "text",
            "label": "Balance",
            "value": "₹84,250",
            "visible": True,
            "enabled": True,
        },
        {
            "element_id": "EL_005",
            "role": "text",
            "label": "Latest transaction",
            "text": "Amazon — ₹2,340 on 2026-09-14",
            "visible": True,
            "enabled": True,
        },
        {
            "element_id": "EL_006",
            "role": "text",
            "label": "Status",
            "text": "Transaction completed",
            "visible": True,
            "enabled": True,
        },
    ],
}


def test_page_state_to_sanitized_state_preserves_contract_and_context():
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(BANKING_PAGE_STATE)

    assert sanitized["source_page_state_id"] == BANKING_PAGE_STATE["page_state_id"]
    assert sanitized["url"] == BANKING_PAGE_STATE["url"]
    assert sanitized["title"] == BANKING_PAGE_STATE["title"]
    assert sanitized["elements"][0]["text"] == "SecureBank Dashboard"
    assert sanitized["elements"][4]["text"] == "Amazon — [PAYMENT_02] on 2026-09-14"
    assert sanitized["elements"][1]["text"] == "[PERSON_01]"
    assert sanitized["elements"][2]["value"] == "[ACCOUNT_01]"
    assert sanitized["elements"][3]["value"] == "[PAYMENT_01]"


def test_placeholders_are_consistent_and_mapping_is_local_only():
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(BANKING_PAGE_STATE)

    assert tokenizer.local_mapping["[PERSON_01]"] == "Rahul Sharma"
    assert tokenizer.local_mapping["[ACCOUNT_01]"] == "7845129034"
    assert tokenizer.local_mapping["[PAYMENT_01]"] == "₹84,250"
    assert tokenizer.local_mapping["[PAYMENT_02]"] == "₹2,340"

    serialized = json.dumps(sanitized, ensure_ascii=False)
    for raw_value in tokenizer.local_mapping.values():
        assert raw_value not in serialized

    assert "token_map" not in sanitized
    assert "raw_to_token_map" not in sanitized
    assert sanitized["privacy_summary"]["verification_passed"] is True


def test_mixed_sensitive_and_safe_content_is_partially_redacted():
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(BANKING_PAGE_STATE)

    transaction = sanitized["elements"][4]["text"]
    assert "Amazon" in transaction
    assert "2026-09-14" in transaction
    assert "₹2,340" not in transaction
    assert "[PAYMENT_02]" in transaction

    status = sanitized["elements"][5]
    assert status["text"] == "Transaction completed"
    assert status["sensitivity"] == "NONE"


def test_email_inside_visible_text_is_redacted_without_losing_context():
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(BANKING_PAGE_STATE)
    visible_text = sanitized["visible_text"]

    assert "SecureBank Dashboard" in visible_text
    assert "rahul.sharma@gmail.com" not in visible_text
    assert "[EMAIL_01]" in visible_text


def test_element_ids_are_preserved_and_not_derived_from_secrets():
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(BANKING_PAGE_STATE)

    assert [e["element_id"] for e in sanitized["elements"]] == [
        "EL_001", "EL_002", "EL_003", "EL_004", "EL_005", "EL_006"
    ]
    assert all(raw not in e["element_id"] for raw in tokenizer.local_mapping.values() for e in sanitized["elements"])


def test_convenience_api_keeps_mapping_separate_from_agent_payload():
    sanitized, local_mapping = sanitize_page_state(BANKING_PAGE_STATE)
    serialized = json.dumps(sanitized, ensure_ascii=False)

    assert local_mapping["[PERSON_01]"] == "Rahul Sharma"
    assert "Rahul Sharma" not in serialized
    assert "7845129034" not in serialized
    assert "₹84,250" not in serialized


def test_clear_local_memory_removes_original_mapping():
    tokenizer = PrivacyTokenizer()
    tokenizer.sanitize_page_state(BANKING_PAGE_STATE)
    assert tokenizer.local_mapping
    tokenizer.clear_local_memory()
    assert tokenizer.local_mapping == {}


def test_day2_schema_shape_is_satisfied_for_generated_state():
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(BANKING_PAGE_STATE)

    required = {
        "schema_version", "sanitized_state_id", "source_page_state_id", "captured_at",
        "url", "title", "visible_text", "elements", "privacy_summary"
    }
    assert required.issubset(sanitized)
    assert sanitized["sanitized_state_id"].startswith("SPS_")
    assert sanitized["privacy_summary"]["redaction_count"] >= 4
    assert sanitized["privacy_summary"]["verification_passed"] is True

    for element in sanitized["elements"]:
        assert element["sensitivity"] in {"NONE", "SENSITIVE_CONTEXT", "REDACTED"}
        assert "element_id" in element
        assert "role" in element
        assert "visible" in element
        assert "enabled" in element


def test_embedded_sensitive_spans_preserve_safe_context():
    tokenizer = PrivacyTokenizer()

    cases = [
        ("Customer: Rahul Sharma", "Customer: [PERSON_01]", "Rahul Sharma"),
        ("Contact Rahul Sharma at rahul@gmail.com", "Contact [PERSON_01] at [EMAIL_01]", "Rahul Sharma"),
        ("Account holder Rahul Sharma has balance ₹84,250", "Account holder [PERSON_01] has balance [PAYMENT_01]", "Rahul Sharma"),
    ]

    for raw, expected, original in cases:
        sanitized, modified = tokenizer.sanitize_node(raw)
        assert modified is True
        assert sanitized == expected
        assert original not in sanitized


def test_message_content_is_redacted_without_losing_safe_prefix():
    tokenizer = PrivacyTokenizer()
    sanitized, modified = tokenizer.sanitize_node(
        "Please keep this private conversation confidential"
    )

    assert modified is True
    assert sanitized == "Please keep this [MESSAGE_01] [MESSAGE_02]"
    assert "Please keep this" in sanitized
    assert "private conversation" not in sanitized
    assert "confidential" not in sanitized


def test_category_specific_tokens_do_not_collide_for_same_raw_value():
    tokenizer = PrivacyTokenizer()
    phone, _ = tokenizer.sanitize_node("9876543210", "phone")
    account, _ = tokenizer.sanitize_node("9876543210", "account")
    repeated_phone, _ = tokenizer.sanitize_node("9876543210", "phone")

    assert phone == "[PHONE_01]"
    assert account == "[ACCOUNT_01]"
    assert repeated_phone == phone


def test_contextual_password_replaces_only_the_secret():
    tokenizer = PrivacyTokenizer()
    sanitized, modified = tokenizer.sanitize_node("Password: DemoPass123!", "password")

    assert modified is True
    assert sanitized == "Password: [PASSWORD_01]"
    assert "DemoPass123!" not in sanitized
    assert tokenizer.local_mapping == {"[PASSWORD_01]": "DemoPass123!"}


def test_full_state_redaction_has_no_original_message_or_name_values():
    raw_state = {
        "schema_version": "1.0",
        "page_state_id": "PS_redaction_001",
        "captured_at": "2026-09-15T00:00:00Z",
        "url": "https://example.local",
        "title": "Private page",
        "visible_text": "Customer: Rahul Sharma. Please keep this private conversation confidential.",
        "elements": [
            {
                "element_id": "EL_001",
                "role": "text",
                "label": "Customer",
                "text": "Customer: Rahul Sharma",
                "visible": True,
                "enabled": True,
            },
            {
                "element_id": "EL_002",
                "role": "text",
                "label": "Message",
                "text": "Please keep this private conversation confidential",
                "visible": True,
                "enabled": True,
            },
        ],
    }
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(raw_state)
    serialized = json.dumps(sanitized, ensure_ascii=False)

    assert "Rahul Sharma" not in serialized
    assert "private conversation" not in serialized
    assert "confidential" not in serialized
    assert "Customer:" in serialized
    assert "Please keep this" in serialized
    assert "token_map" not in sanitized
    assert sanitized["privacy_summary"]["verification_passed"] is True
