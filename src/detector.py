import re
from typing import Dict, Any, List

class PrivacyDetector:
    """
    Core detection engine for identifying private information while filtering out
    similar-looking benign edge cases using contextual rules.
    """

    # Basic regex patterns for candidate extraction
    EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    INDIAN_PHONE_REGEX = re.compile(r'^(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}$')
    CURRENCY_REGEX = re.compile(r'(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?', re.IGNORECASE)
    SSN_REGEX = re.compile(r"\d{3}[- ]?\d{2}[- ]?\d{4}")
    PAN_REGEX = re.compile(r"(?:\d[ -]?){12,18}\d")
    MASKED_PAN_REGEX = re.compile(r"(?:[*xX#]{4}[ -]?){3}\d{4}")

    CONTEXT_KEYWORDS = {
        "password": [
            "password:", "enter password:", "current password:",
            "new password:", "confirm password:", "password =", "otp:", "otp ="
        ],
        "account": [
            "account no:", "a/c no:", "bank account:", "account number:"
        ],
        "payment": [
            "amount:", "balance:"
        ],
        "message": [
            "private conversation", "confidential", "don't tell anyone",
            "verification details", "reply to me privately", "send the bank details"
        ],
        "financial": [
            "bank account", "banking details", "credit card", "debit card", "transaction history",
            "transaction details", "payment details", "routing number", "wire transfer", "salary",
            "tax return", "investment portfolio"
        ],
        "medical": [
            "medical record", "diagnosis", "prescription", "medication", "symptoms",
            "patient", "health insurance", "blood type", "lab result"
        ],
        "authentication": [
            "sign in credentials", "log in credentials", "login credentials", "verification code", "security answer",
            "api key", "auth token", "passcode", "recovery code", "two-factor"
        ],
        "private_communication": [
            "private conversation", "direct message", "personal message", "reply privately",
            "do not share this", "don't tell anyone"
        ],
        "confidential": [
            "confidential", "internal use only", "proprietary", "trade secret",
            "restricted information", "do not distribute", "under nda"
        ],
    }

    NEGATIVE_CONTEXTS = {
        "account": ["order id:", "product id:", "invoice no:", "pin code:", "year:", "reference:"],
        "payment": ["page", "quantity:", "distance:", "score:", "id:"],
        "name": ["amazon india", "google chrome", "smart banking", "order summary", "privacy settings", "student portal"],
        "address": ["home page", "shipping address", "address settings"]
    }

    def detect_email(self, text: str) -> bool:
        return bool(self.EMAIL_REGEX.fullmatch(text.strip()))

    def detect_phone(self, text: str) -> bool:
        clean_text = text.strip()
        # Exclude plain sequences with negative keywords like order IDs / product IDs
        if any(keyword in clean_text.lower() for keyword in ["order", "product"]):
            return False

        # Strip phone formatting for length checking
        digits_only = re.sub(r'\D', '', clean_text)

        # Check standard 10-digit Indian mobile range (starts with 6-9) or 12-digit with 91 prefix
        if len(digits_only) == 10 and digits_only[0] in '6789':
            return True
        elif len(digits_only) == 12 and digits_only.startswith('91') and digits_only[2] in '6789':
            return True

        return False

    def detect_ssn(self, text: str) -> bool:
        return bool(self.SSN_REGEX.fullmatch(text.strip()))

    def detect_pan(self, text: str) -> bool:
        clean_text = text.strip()
        digits_only = re.sub(r"[ -]", "", clean_text)
        return bool(
            (self.PAN_REGEX.fullmatch(clean_text) and 13 <= len(digits_only) <= 19)
            or self.MASKED_PAN_REGEX.fullmatch(clean_text)
        )

    def detect_name(self, text: str) -> bool:
        clean_text = text.strip()
        if clean_text.lower() in self.NEGATIVE_CONTEXTS["name"]:
            return False

        words = clean_text.split()
        # Require a multi-word proper-capitalization pattern for human names in context.
        if 2 <= len(words) <= 4 and all(w.istitle() for w in words):
            return True
        return False

    def detect_address(self, text: str) -> bool:
        clean_text = text.strip()
        if clean_text.lower() in self.NEGATIVE_CONTEXTS["address"]:
            return False

        # Require comma-separated locality/state structure or street prefixes
        address_indicators = ["road", "mg road", "street", "plot", "flat", "village", "sector"]
        has_multiple_parts = "," in clean_text
        has_street_indicator = any(indicator in clean_text.lower() for indicator in address_indicators)

        return has_multiple_parts or has_street_indicator

    def detect_password(self, text: str) -> bool:
        clean_text = text.lower().strip()
        # Require actual assignment/entry context rather than just field labels
        for prefix in self.CONTEXT_KEYWORDS["password"]:
            if clean_text.startswith(prefix):
                return True
        return bool(re.fullmatch(r"\d{4,8}", clean_text))

    def detect_payment(self, text: str) -> bool:
        clean_text = text.strip()
        if any(neg in clean_text.lower() for neg in self.NEGATIVE_CONTEXTS["payment"]):
            return False

        # Matches currency symbols/prefixes or financial context prefixes
        if self.CURRENCY_REGEX.search(clean_text):
            return True
        if any(prefix in clean_text.lower() for prefix in self.CONTEXT_KEYWORDS["payment"]):
            return True
        return False

    def detect_account(self, text: str) -> bool:
        clean_text = text.strip()
        clean_lower = clean_text.lower()

        # Exclude product/order IDs
        if any(neg in clean_lower for neg in self.NEGATIVE_CONTEXTS["account"]):
            return False

        # Explicit account labels
        if any(prefix in clean_lower for prefix in self.CONTEXT_KEYWORDS["account"]):
            return True

        # Check raw spaced account number formats (10-12 digits without negative context)
        digits_only = re.sub(r'\s', '', clean_text)
        if digits_only.isdigit() and len(digits_only) in [10, 11, 12]:
            return True

        return False

    def detect_message(self, text: str) -> bool:
        clean_lower = text.lower()
        return any(keyword in clean_lower for keyword in self.CONTEXT_KEYWORDS["message"])

    def detect_sensitive_context(self, text: str, category: str) -> bool:
        """Detect a small, explicit set of high-risk context phrases."""
        clean_lower = text.lower()
        return any(keyword in clean_lower for keyword in self.CONTEXT_KEYWORDS.get(category, []))

    def detect_financial(self, text: str) -> bool:
        return self.detect_sensitive_context(text, "financial")

    def detect_medical(self, text: str) -> bool:
        return self.detect_sensitive_context(text, "medical")

    def detect_authentication(self, text: str) -> bool:
        return self.detect_sensitive_context(text, "authentication")

    def detect_private_communication(self, text: str) -> bool:
        return self.detect_sensitive_context(text, "private_communication")

    def detect_confidential(self, text: str) -> bool:
        return self.detect_sensitive_context(text, "confidential")


def evaluate_item(category: str, text: str) -> bool:
    detector = PrivacyDetector()
    method_map = {
        "email": detector.detect_email,
        "phone": detector.detect_phone,
        "name": detector.detect_name,
        "address": detector.detect_address,
        "password": detector.detect_password,
        "ssn": detector.detect_ssn,
        "pan": detector.detect_pan,
        "payment": detector.detect_payment,
        "account": detector.detect_account,
        "message": detector.detect_message,
        "financial": detector.detect_financial,
        "medical": detector.detect_medical,
        "authentication": detector.detect_authentication,
        "private_communication": detector.detect_private_communication,
        "confidential": detector.detect_confidential,
    }

    handler = method_map.get(category.lower())
    if handler:
        return handler(text)
    return False