import re
import secrets
from typing import Dict, Tuple, List, Any, Optional
from .detector import PrivacyDetector


class PrivacyTokenizer:
    """
    Sanitizes Privacy Engine input into safe structural placeholders while keeping
    the original-value mapping only in local in-memory state.

    Day 2 contract:
        PageState -> SanitizedPageState

    The mapping is intentionally a property of this local tokenizer instance and
    is never copied into the SanitizedPageState output.
    """

    CATEGORY_ORDER = (
        "email",
        "phone",
        "password",
        "account",
        "payment",
        "address",
        "name",
        "message",
    )

    TOKEN_PREFIXES = {
        "EMAIL": "EMAIL",
        "PHONE": "PHONE",
        "NAME": "PERSON",
        "ADDRESS": "ADDRESS",
        "PASSWORD": "PASSWORD",
        "PAYMENT": "PAYMENT",
        "ACCOUNT": "ACCOUNT",
        "MESSAGE": "MESSAGE",
    }

    # These patterns are used only to locate sensitive spans inside otherwise
    # useful text. Detection remains owned by PrivacyDetector.
    EMAIL_SPAN_REGEX = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )
    CURRENCY_SPAN_REGEX = re.compile(
        r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?", re.IGNORECASE
    )
    PHONE_SPAN_REGEX = re.compile(
        r"(?<!\d)(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}(?!\d)"
    )
    DIGIT_SPAN_REGEX = re.compile(r"(?<!\d)(?:\d[\s-]?){9,11}\d(?!\d)")
    ADDRESS_SPAN_REGEX = re.compile(
        r"(?<!\w)(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?!\w)"
    )
    MESSAGE_SPAN_REGEX = re.compile(
        r"private\s+conversation|confidential|don't\s+tell\s+anyone|"
        r"verification\s+details|reply\s+to\s+me\s+privately|"
        r"send\s+the\s+bank\s+details",
        re.IGNORECASE,
    )

    CONTEXT_PATTERNS = {
        "name": re.compile(
            r"(?i)(?P<prefix>\b(?:full\s+)?name\s*[:=-]\s*)(?P<value>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
        ),
        "account": re.compile(
            r"(?i)(?P<prefix>\b(?:account\s*(?:no\.?|number)?|a/c\s*no\.?)\s*[:=-]?\s*)(?P<value>(?:\d[\s-]?){9,11}\d)"
        ),
        "payment": re.compile(
            r"(?i)(?P<prefix>\b(?:amount|balance)\s*[:=-]\s*)(?P<value>(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?)"
        ),
        "password": re.compile(
            r"(?i)(?P<prefix>\b(?:password|enter\s+password|current\s+password|new\s+password|confirm\s+password)\s*[:=-]\s*)(?P<value>\S+)"
        ),
        "email": re.compile(
            r"(?i)(?P<prefix>\b(?:email|e-mail)\s*[:=-]\s*)(?P<value>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
        ),
        "phone": re.compile(
            r"(?i)(?P<prefix>\b(?:phone|mobile|contact)\s*(?:number|no\.?)?\s*[:=-]\s*)(?P<value>(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5})"
        ),
        "name": re.compile(
            r"(?i)(?P<prefix>\b(?:customer|contact|account\s+holder|full\s+name|name)\s*[:=-]?\s*)(?P<value>[A-Z][a-z]+\s+[A-Z][a-z]+)"
        ),
    }

    def __init__(self):
        self.detector = PrivacyDetector()
        # Local, in-memory token -> original mapping. Never serialized.
        self.token_map: Dict[str, str] = {}
        # Local reverse mapping used for stable placeholders.
        self.raw_to_token_map: Dict[Tuple[str, str], str] = {}
        self.category_counters: Dict[str, int] = {}

    @property
    def local_mapping(self) -> Dict[str, str]:
        """Return the local mapping object; it is never part of SanitizedPageState."""
        return self.token_map

    def _generate_token(self, category: str, raw_value: str) -> str:
        raw_key = raw_value.strip()
        category_upper = category.upper()
        mapping_key = (category_upper, raw_key)
        if mapping_key in self.raw_to_token_map:
            return self.raw_to_token_map[mapping_key]

        prefix = self.TOKEN_PREFIXES.get(category_upper, "DATA")
        count = self.category_counters.get(prefix, 0) + 1
        self.category_counters[prefix] = count

        token = f"[{prefix}_{count:02d}]"
        self.token_map[token] = raw_key
        self.raw_to_token_map[mapping_key] = token
        return token

    def _detected(self, category: str, value: str) -> bool:
        method = getattr(self.detector, f"detect_{category}", None)
        return bool(method and method(value))

    def _span_matches(self, text: str, category_hint: Optional[str] = None) -> List[Tuple[int, int, str]]:
        """Return validated sensitive spans as (start, end, category)."""
        if not text:
            return []

        categories = [category_hint] if category_hint else list(self.CATEGORY_ORDER)
        matches: List[Tuple[int, int, str]] = []

        # Explicit field context has priority because a number can be either a
        # phone number or an account number depending on its label.
        for cat in categories:
            pattern = self.CONTEXT_PATTERNS.get(cat)
            if pattern:
                for match in pattern.finditer(text):
                    value = match.group("value")
                    detected_value = match.group(0) if cat == "password" else value
                    if self._detected(cat, detected_value):
                        matches.append((match.start("value"), match.end("value"), cat))

        # Generic span extraction is used for mixed text such as:
        # "Amazon — ₹2,340" or "Contact rahul@gmail.com today".
        generic_patterns = {
            "email": self.EMAIL_SPAN_REGEX,
            "phone": self.PHONE_SPAN_REGEX,
            "payment": self.CURRENCY_SPAN_REGEX,
            "account": self.DIGIT_SPAN_REGEX,
            "address": self.ADDRESS_SPAN_REGEX,
            "message": self.MESSAGE_SPAN_REGEX,
        }
        for cat in categories:
            pattern = generic_patterns.get(cat)
            if not pattern:
                continue
            for match in pattern.finditer(text):
                value = match.group(0)
                if self._detected(cat, value):
                    matches.append((match.start(), match.end(), cat))

        # Whole-value categories are deliberately conservative. They are most
        # reliable for PageState fields such as label/value pairs.
        if not matches and category_hint and self._detected(category_hint, text.strip()):
            stripped_start = len(text) - len(text.lstrip())
            stripped_end = len(text.rstrip())
            if stripped_start < stripped_end:
                matches.append((stripped_start, stripped_end, category_hint))
        elif not matches:
            for cat in ("password", "address", "name", "message"):
                if self._detected(cat, text.strip()):
                    stripped_start = len(text) - len(text.lstrip())
                    stripped_end = len(text.rstrip())
                    if stripped_start < stripped_end:
                        matches.append((stripped_start, stripped_end, cat))
                    break

        # De-duplicate and resolve overlaps by keeping the first/highest-priority
        # validated span. This avoids double-tokenizing a single sensitive value.
        matches.sort(key=lambda item: (item[0], item[1], self.CATEGORY_ORDER.index(item[2]) if item[2] in self.CATEGORY_ORDER else 99))
        selected: List[Tuple[int, int, str]] = []
        for candidate in matches:
            if selected and candidate[0] < selected[-1][1]:
                continue
            selected.append(candidate)
        return selected

    def sanitize_node(self, text: str, category_hint: str = None) -> Tuple[str, bool]:
        """Sanitize one text node, preserving non-sensitive surrounding context."""
        if not isinstance(text, str) or not text.strip():
            return text, False

        matches = self._span_matches(text, category_hint=category_hint)
        if not matches:
            return text, False

        pieces: List[str] = []
        cursor = 0
        for start, end, category in matches:
            raw_value = text[start:end]
            token = self._generate_token(category, raw_value)
            pieces.append(text[cursor:start])
            pieces.append(token)
            cursor = end
        pieces.append(text[cursor:])
        return "".join(pieces), True

    @staticmethod
    def _category_hint(label: str, field_name: str = "") -> Optional[str]:
        context = f"{label or ''} {field_name or ''}".lower()
        hints = (
            ("email", "email"),
            ("e-mail", "email"),
            ("phone", "phone"),
            ("mobile", "phone"),
            ("contact", "phone"),
            ("password", "password"),
            ("otp", "password"),
            ("account", "account"),
            ("a/c", "account"),
            ("balance", "payment"),
            ("amount", "payment"),
            ("salary", "payment"),
            ("price", "payment"),
            ("name", "name"),
            ("address", "address"),
            ("message", "message"),
            ("private", "message"),
            ("confidential", "message"),
        )
        for keyword, category in hints:
            if keyword in context:
                return category
        return None

    def _sanitize_element(self, element: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], int]:
        sanitized = {
            key: element[key]
            for key in (
                "element_id", "role", "type", "label", "text", "value",
                "visible", "enabled", "bounds"
            )
            if key in element
        }

        categories: List[str] = []
        redaction_count = 0
        placeholders: List[str] = []

        label = element.get("label", "") or ""

        # Label itself is context, not a secret. Sanitize text/value independently
        # so mixed content is preserved.
        for field_name in ("text", "value"):
            if field_name not in sanitized or sanitized[field_name] is None:
                continue
            raw_text = sanitized[field_name]
            if not isinstance(raw_text, str):
                continue

            hint = self._category_hint(label, field_name)
            sanitized_text, modified = self.sanitize_node(raw_text, hint)
            sanitized[field_name] = sanitized_text
            if modified:
                redaction_count += sum(1 for _ in self._span_matches(raw_text, hint))
                for _, _, category in self._span_matches(raw_text, hint):
                    if category.upper() not in categories:
                        categories.append(category.upper())
                # Capture placeholders created by this element without exposing
                # the originals in the output object.
                for token in self.token_map:
                    if token in sanitized_text and token not in placeholders:
                        placeholders.append(token)

        # Sensitive-context messages are flagged, but the message itself is not
        # indiscriminately erased. Any exact PII inside it has already been
        # replaced above.
        context_text = " ".join(
            str(element.get(field, "") or "") for field in ("label", "text", "value")
        )
        message_sensitive = self.detector.detect_message(context_text)
        if message_sensitive:
            categories.append("MESSAGE")

        if redaction_count:
            sanitized["sensitivity"] = "REDACTED"
            if len(placeholders) == 1 and sanitized.get("text") == placeholders[0] or len(placeholders) == 1 and sanitized.get("value") == placeholders[0]:
                sanitized["redaction_placeholder"] = placeholders[0]
        elif message_sensitive:
            sanitized["sensitivity"] = "SENSITIVE_CONTEXT"
        else:
            sanitized["sensitivity"] = "NONE"

        return sanitized, categories, redaction_count

    @staticmethod
    def _new_sanitized_state_id() -> str:
        return f"SPS_{secrets.token_urlsafe(8)}"

    def sanitize_page_state(self, page_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a raw PageState to the project's frozen SanitizedPageState shape.

        The returned object contains no local mapping. The original values remain
        only in ``self.token_map`` for the lifetime of this tokenizer instance.
        """
        if not isinstance(page_state, dict):
            raise TypeError("page_state must be a dictionary")
        required = ("schema_version", "page_state_id", "captured_at", "url", "title", "visible_text", "elements")
        missing = [key for key in required if key not in page_state]
        if missing:
            raise ValueError(f"PageState missing required fields: {', '.join(missing)}")

        # Process structured elements first so placeholder numbering follows the
        # PageState's natural element order (for example balance -> MONEY_01,
        # transaction amount -> MONEY_02). Visible text then reuses those tokens.
        sanitized_elements: List[Dict[str, Any]] = []
        categories_seen: List[str] = []
        redaction_count = 0
        sensitive_context_detected = False

        for element in page_state.get("elements", []):
            sanitized_element, categories, count = self._sanitize_element(element)
            sanitized_elements.append(sanitized_element)
            redaction_count += count
            for category in categories:
                if category not in categories_seen:
                    categories_seen.append(category)
            if sanitized_element["sensitivity"] == "SENSITIVE_CONTEXT":
                sensitive_context_detected = True
            if "MESSAGE" in categories:
                sensitive_context_detected = True

        # Sanitize visible text after structured fields so repeated values reuse
        # the same local placeholders. Context around the sensitive span survives.
        raw_visible_text = str(page_state.get("visible_text", ""))
        sanitized_visible_text, visible_modified = self.sanitize_node(raw_visible_text)
        if visible_modified:
            visible_matches = self._span_matches(raw_visible_text)
            redaction_count += len(visible_matches)
            for _, _, category in visible_matches:
                category = category.upper()
                if category not in categories_seen:
                    categories_seen.append(category)

        # If visible_text contains sensitive context, expose only the boolean in
        # the privacy summary. Never store the raw context separately.
        if self.detector.detect_message(raw_visible_text):
            sensitive_context_detected = True
            if "MESSAGE" not in categories_seen:
                categories_seen.append("MESSAGE")

        sanitized_state = {
            "schema_version": page_state["schema_version"],
            "sanitized_state_id": self._new_sanitized_state_id(),
            "source_page_state_id": page_state["page_state_id"],
            "captured_at": page_state["captured_at"],
            "url": page_state["url"],
            "title": page_state["title"],
            "visible_text": sanitized_visible_text,
            "elements": sanitized_elements,
            "privacy_summary": {
                "sensitive_context_detected": sensitive_context_detected,
                "redaction_count": redaction_count,
                "categories": categories_seen,
                "verification_passed": self._verify_no_original_values(sanitized_state_values={}),
            },
        }

        # Preserve optional non-sensitive structural context from the frozen
        # contract. These fields contain no mapping data.
        for key in ("accessibility_snapshot", "visual_summary", "error"):
            if key in page_state:
                value = page_state[key]
                if isinstance(value, str):
                    value, _ = self.sanitize_node(value)
                sanitized_state[key] = value

        # Re-run verification against the complete output after construction.
        sanitized_state["privacy_summary"]["verification_passed"] = self._verify_no_original_values(sanitized_state)
        return sanitized_state

    def _verify_no_original_values(self, sanitized_state_values: Dict[str, Any]) -> bool:
        """Verify that none of the locally stored raw values appear in Agent input."""
        if not self.token_map:
            return True
        serialized = repr(sanitized_state_values)
        return all(raw_value not in serialized for raw_value in self.token_map.values())

    def restore_tokens(self, sanitized_text: str) -> str:
        """Resolve placeholders locally for browser-side use only."""
        restored_text = sanitized_text
        for token, raw_value in self.token_map.items():
            restored_text = restored_text.replace(token, raw_value)
        return restored_text

    def clear_local_memory(self):
        """Wipe the local temporary token mapping."""
        self.token_map.clear()
        self.raw_to_token_map.clear()
        self.category_counters.clear()


def sanitize_text(text: str, category_hint: str = None) -> str:
    """Backward-compatible helper for sanitizing a single string."""
    tokenizer = PrivacyTokenizer()
    sanitized, _ = tokenizer.sanitize_node(text, category_hint)
    return sanitized


def sanitize_page_state(page_state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Convenience API returning sanitized state and a *separate* local mapping.

    Callers must keep the second value local; it is intentionally not embedded in
    the returned SanitizedPageState.
    """
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(page_state)
    return sanitized, tokenizer.local_mapping
