"""
AgentArora Privacy Engine Package.

Provides local pattern detection and structural tokenization for PII/sensitive data.
"""

from .detector import PrivacyDetector, evaluate_item
from .tokenizer import PrivacyTokenizer, sanitize_text

__version__ = "1.0.0"
__all__ = [
    "PrivacyDetector",
    "PrivacyTokenizer",
    "evaluate_item",
    "sanitize_text",
]