import json
import re
import secrets
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from typing import Dict, Tuple, List, Any, Optional
from .detector import PrivacyDetector


class PrivacyTokenizer:
    """Sanitize PageState into Agent-safe structural placeholders."""

    CATEGORY_ORDER = (
        "email", "phone", "password", "ssn", "pan", "account", "payment", "address", "name", "message"
    )

    TOKEN_PREFIXES = {
        "EMAIL": "EMAIL", "PHONE": "PHONE", "NAME": "PERSON", "ADDRESS": "ADDRESS",
        "PASSWORD": "PASSWORD", "SSN": "SSN", "PAN": "PAN", "PAYMENT": "PAYMENT", "ACCOUNT": "ACCOUNT", "MESSAGE": "MESSAGE",
    }

    EMAIL_SPAN_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    CURRENCY_SPAN_REGEX = re.compile(r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?", re.IGNORECASE)
    PHONE_SPAN_REGEX = re.compile(r"(?<!\d)(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}(?!\d)")
    DIGIT_SPAN_REGEX = re.compile(r"(?<!\d)(?:\d[\s-]?){9,11}\d(?!\d)")
    SSN_SPAN_REGEX = re.compile(r"(?<!\d)\d{3}[- ]?\d{2}[- ]?\d{4}(?!\d)")
    PAN_SPAN_REGEX = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
    MASKED_PAN_SPAN_REGEX = re.compile(r"(?<!\w)(?:[*xX#]{4}[ -]?){3}\d{4}(?!\d)")
    ADDRESS_SPAN_REGEX = re.compile(
        r"(?<!\w)(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*"
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?!\w)"
    )
    MESSAGE_SPAN_REGEX = re.compile(
        r"private\s+conversation|confidential|don't\s+tell\s+anyone|"
        r"verification\s+details|reply\s+to\s+me\s+privately|send\s+the\s+bank\s+details",
        re.IGNORECASE,
    )

    CONTEXT_PATTERNS = {
        "name": re.compile(r"(?i)\b(?:customer|contact|account\s+holder|full\s+name|name)\s*[:=-]?\s*(?P<value>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"),
        "account": re.compile(r"(?i)\b(?:account\s*(?:no\.?|number)?|a/c\s*no\.?)\s*[:=-]?\s*(?P<value>(?:\d[\s-]?){9,11}\d)"),
        "payment": re.compile(r"(?i)\b(?:amount|balance)\s*[:=-]\s*(?P<value>(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?)"),
        "ssn": re.compile(r"(?i)\b(?:ssn|social\s+security(?:\s+number)?)\s*[:=-]?\s*(?P<value>\d{3}[- ]?\d{2}[- ]?\d{4})"),
        "pan": re.compile(r"(?i)\b(?:pan|card\s+number|credit\s+card|debit\s+card)\s*[:=-]?\s*(?P<value>(?:(?:\d[ -]?){12,18}\d|(?:[*xX#]{4}[ -]?){3}\d{4}))"),
        "password": re.compile(r"(?i)\b(?:password|enter\s+password|current\s+password|new\s+password|confirm\s+password|otp)\s*[:=-]?\s*(?P<value>\S+)"),
        "email": re.compile(r"(?i)\b(?:email|e-mail)\s*[:=-]\s*(?P<value>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
        "phone": re.compile(r"(?i)\b(?:phone|mobile|contact)\s*(?:number|no\.?)?\s*[:=-]\s*(?P<value>(?:\+?91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5})"),
    }

    MAX_ELEMENTS = 500
    MAX_VISIBLE_TEXT = 20_000
    MAX_TITLE = 300
    MAX_URL = 2_048
    MAX_NESTED_DEPTH = 8

    def __init__(self):
        self.detector = PrivacyDetector()
        self.token_map: Dict[str, str] = {}
        self.raw_to_token_map: Dict[Tuple[str, str], str] = {}
        self.category_counters: Dict[str, int] = {}

    @property
    def local_mapping(self) -> Dict[str, str]:
        """Return a defensive copy so callers cannot mutate sensitive local state."""
        return dict(self.token_map)

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
        if not text:
            return []
        categories = [category_hint] if category_hint else list(self.CATEGORY_ORDER)
        matches: List[Tuple[int, int, str]] = []

        for cat in categories:
            pattern = self.CONTEXT_PATTERNS.get(cat)
            if pattern:
                for match in pattern.finditer(text):
                    value = match.group("value")
                    detected_value = match.group(0) if cat == "password" else value
                    if self._detected(cat, detected_value):
                        matches.append((match.start("value"), match.end("value"), cat))

        generic_patterns = {
            "email": self.EMAIL_SPAN_REGEX,
            "phone": self.PHONE_SPAN_REGEX,
            "payment": self.CURRENCY_SPAN_REGEX,
            "ssn": self.SSN_SPAN_REGEX,
            "pan": re.compile(
                rf"{self.PAN_SPAN_REGEX.pattern}|{self.MASKED_PAN_SPAN_REGEX.pattern}"
            ),
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

        if not matches and category_hint and self._detected(category_hint, text.strip()):
            start = len(text) - len(text.lstrip())
            end = len(text.rstrip())
            if start < end:
                matches.append((start, end, category_hint))
        elif not matches:
            for cat in ("password", "address", "name", "message"):
                if self._detected(cat, text.strip()):
                    start = len(text) - len(text.lstrip())
                    end = len(text.rstrip())
                    if start < end:
                        matches.append((start, end, cat))
                    break

        matches.sort(key=lambda item: (item[0], item[1], self.CATEGORY_ORDER.index(item[2])))
        selected: List[Tuple[int, int, str]] = []
        for candidate in matches:
            if selected and candidate[0] < selected[-1][1]:
                continue
            selected.append(candidate)
        return selected

    def sanitize_node(self, text: str, category_hint: str = None) -> Tuple[str, bool]:
        if not isinstance(text, str) or not text.strip():
            return text, False

        working = text
        reused = False
        if category_hint is None:
            for (_, raw), token in sorted(self.raw_to_token_map.items(), key=lambda item: len(item[0][1]), reverse=True):
                if raw and raw in working:
                    working = working.replace(raw, token)
                    reused = True

        matches = self._span_matches(working, category_hint=category_hint)
        if not matches:
            return working, reused

        pieces: List[str] = []
        cursor = 0
        for start, end, category in matches:
            token = self._generate_token(category, working[start:end])
            pieces.extend((working[cursor:start], token))
            cursor = end
        pieces.append(working[cursor:])
        return "".join(pieces), True

    @staticmethod
    def _category_hint(label: str, field_name: str = "") -> Optional[str]:
        context = f"{label or ''} {field_name or ''}".lower()
        hints = (
            ("email", "email"), ("e-mail", "email"), ("phone", "phone"), ("mobile", "phone"),
            ("contact", "phone"), ("password", "password"), ("otp", "password"),
            ("ssn", "ssn"), ("social security", "ssn"),
            ("pan", "pan"), ("card number", "pan"), ("credit card", "pan"), ("debit card", "pan"),
            ("account", "account"), ("a/c", "account"), ("balance", "payment"),
            ("amount", "payment"), ("salary", "payment"), ("price", "payment"),
            ("name", "name"), ("address", "address"), ("message", "message"),
            ("private", "message"), ("confidential", "message"),
        )
        for keyword, category in hints:
            if keyword in context:
                return category
        return None

    def _sanitize_element(self, element: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], int]:
        sanitized = {
            key: element[key]
            for key in ("element_id", "role", "type", "label", "text", "value", "visible", "enabled", "bounds")
            if key in element
        }
        categories: List[str] = []
        redaction_count = 0
        placeholders: List[str] = []
        raw_label = str(element.get("label", "") or "")

        if "label" in sanitized:
            hint = self._category_hint(raw_label, "label")
            sanitized_label, modified = self.sanitize_node(raw_label, hint)
            sanitized["label"] = sanitized_label
            if modified:
                matches = self._span_matches(raw_label, hint)
                redaction_count += len(matches)
                for _, _, category in matches:
                    upper = category.upper()
                    if upper not in categories:
                        categories.append(upper)
                placeholders.extend(token for token in self.token_map if token in sanitized_label and token not in placeholders)

        for field_name in ("text", "value"):
            if field_name not in sanitized or sanitized[field_name] is None:
                continue
            raw_text = sanitized[field_name]
            if not isinstance(raw_text, str):
                continue
            hint = self._category_hint(raw_label, field_name)
            sanitized_text, modified = self.sanitize_node(raw_text, hint)
            sanitized[field_name] = sanitized_text
            if modified:
                matches = self._span_matches(raw_text, hint)
                redaction_count += len(matches)
                for _, _, category in matches:
                    upper = category.upper()
                    if upper not in categories:
                        categories.append(upper)
                placeholders.extend(token for token in self.token_map if token in sanitized_text and token not in placeholders)

        context_text = " ".join(str(element.get(field, "") or "") for field in ("label", "text", "value"))
        if self.detector.detect_message(context_text) and "MESSAGE" not in categories:
            categories.append("MESSAGE")

        if redaction_count:
            sanitized["sensitivity"] = "REDACTED"
            if len(placeholders) == 1 and any(sanitized.get(field) == placeholders[0] for field in ("label", "text", "value")):
                sanitized["redaction_placeholder"] = placeholders[0]
        elif "MESSAGE" in categories:
            sanitized["sensitivity"] = "SENSITIVE_CONTEXT"
        else:
            sanitized["sensitivity"] = "NONE"
        return sanitized, categories, redaction_count

    @staticmethod
    def _new_sanitized_state_id() -> str:
        return f"SPS_{secrets.token_urlsafe(8)}"

    def _sanitize_url(self, value: str) -> str:
        try:
            parts = urlsplit(value)
            if not parts.scheme or not parts.netloc:
                return self.sanitize_node(value)[0][: self.MAX_URL]
            hostname = parts.hostname or ""
            port = f":{parts.port}" if parts.port else ""
            decoded_path = unquote(parts.path)
            path = self.sanitize_node(decoded_path)[0]
            path = quote(path, safe="/@[]!$&'()*+,;=-._~")
            return urlunsplit((parts.scheme, hostname + port, path, "", ""))[: self.MAX_URL]
        except ValueError:
            return self.sanitize_node(value)[0][: self.MAX_URL]

    def _sanitize_recursive(self, value: Any, depth: int = 0) -> Any:
        if depth > self.MAX_NESTED_DEPTH:
            raise ValueError("nested privacy payload exceeds safe depth")
        if isinstance(value, str):
            return self.sanitize_node(value)[0]
        if isinstance(value, dict):
            return {key: self._sanitize_recursive(child, depth + 1) for key, child in value.items()}
        if isinstance(value, list):
            return [self._sanitize_recursive(child, depth + 1) for child in value]
        return value

    def _validate_input_bounds(self, page_state: Dict[str, Any]) -> None:
        elements = page_state.get("elements")
        visible_text = page_state.get("visible_text")
        title = page_state.get("title")
        url = page_state.get("url")
        if not isinstance(elements, list) or len(elements) > self.MAX_ELEMENTS:
            raise ValueError("PageState elements exceed safe limits")
        if not isinstance(visible_text, str) or len(visible_text) > self.MAX_VISIBLE_TEXT:
            raise ValueError("PageState visible_text exceeds safe limits")
        if not isinstance(title, str) or len(title) > self.MAX_TITLE:
            raise ValueError("PageState title exceeds safe limits")
        if not isinstance(url, str) or len(url) > self.MAX_URL:
            raise ValueError("PageState url exceeds safe limits")

    def sanitize_page_state(self, page_state: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(page_state, dict):
            raise TypeError("page_state must be a dictionary")
        required = ("schema_version", "page_state_id", "captured_at", "url", "title", "visible_text", "elements")
        missing = [key for key in required if key not in page_state]
        if missing:
            raise ValueError(f"PageState missing required fields: {', '.join(missing)}")
        self._validate_input_bounds(page_state)

        sanitized_elements: List[Dict[str, Any]] = []
        categories_seen: List[str] = []
        redaction_count = 0
        sensitive_context_detected = False

        for element in page_state.get("elements", []):
            if not isinstance(element, dict):
                raise ValueError("PageState elements must be objects")
            sanitized_element, categories, count = self._sanitize_element(element)
            sanitized_elements.append(sanitized_element)
            redaction_count += count
            for category in categories:
                if category not in categories_seen:
                    categories_seen.append(category)
            if sanitized_element["sensitivity"] == "SENSITIVE_CONTEXT" or "MESSAGE" in categories:
                sensitive_context_detected = True

        raw_title = page_state["title"]
        raw_visible_text = page_state["visible_text"]
        sanitized_title, title_modified = self.sanitize_node(raw_title)
        sanitized_visible_text, visible_modified = self.sanitize_node(raw_visible_text)
        if title_modified:
            matches = self._span_matches(raw_title)
            redaction_count += len(matches)
            for _, _, category in matches:
                upper = category.upper()
                if upper not in categories_seen:
                    categories_seen.append(upper)
        if visible_modified:
            matches = self._span_matches(raw_visible_text)
            redaction_count += len(matches)
            for _, _, category in matches:
                upper = category.upper()
                if upper not in categories_seen:
                    categories_seen.append(upper)
        if self.detector.detect_message(raw_visible_text):
            sensitive_context_detected = True
            if "MESSAGE" not in categories_seen:
                categories_seen.append("MESSAGE")

        sanitized_state = {
            "schema_version": page_state["schema_version"],
            "sanitized_state_id": self._new_sanitized_state_id(),
            "source_page_state_id": page_state["page_state_id"],
            "captured_at": page_state["captured_at"],
            "url": self._sanitize_url(page_state["url"]),
            "title": sanitized_title,
            "visible_text": sanitized_visible_text,
            "elements": sanitized_elements,
            "privacy_summary": {
                "sensitive_context_detected": sensitive_context_detected,
                "redaction_count": redaction_count,
                "categories": categories_seen,
                "verification_passed": False,
            },
        }

        for key in ("accessibility_snapshot", "visual_summary"):
            if key in page_state:
                sanitized_state[key] = self._sanitize_recursive(page_state[key])
        if "error" in page_state:
            sanitized_state["error"] = self._sanitize_recursive(page_state["error"])

        sanitized_state["privacy_summary"]["verification_passed"] = self._verify_no_original_values(sanitized_state)
        return sanitized_state

    def _verify_no_original_values(self, sanitized_state_values: Dict[str, Any]) -> bool:
        payload = json.dumps(sanitized_state_values, ensure_ascii=False, sort_keys=True)
        return all(raw_value not in payload for raw_value in self.token_map.values())

    def restore_tokens(self, sanitized_text: str) -> str:
        restored_text = sanitized_text
        for token, raw_value in self.token_map.items():
            restored_text = restored_text.replace(token, raw_value)
        return restored_text

    def clear_local_memory(self):
        self.token_map.clear()
        self.raw_to_token_map.clear()
        self.category_counters.clear()


def sanitize_text(text: str, category_hint: str = None) -> str:
    tokenizer = PrivacyTokenizer()
    sanitized, _ = tokenizer.sanitize_node(text, category_hint)
    return sanitized


def sanitize_page_state(page_state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    tokenizer = PrivacyTokenizer()
    sanitized = tokenizer.sanitize_page_state(page_state)
    return sanitized, tokenizer.local_mapping
