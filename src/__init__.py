"""
AgentArora Privacy Engine Package.

Provides local pattern detection, structural tokenization, and the task-scoped
PrivacyEngine gateway for PII/sensitive data.
"""

from .detector import PrivacyDetector, evaluate_item
from .privacy_engine import PrivacyEngine
from .tokenizer import PrivacyTokenizer, sanitize_text

__version__ = "1.0.0"
__all__ = [
    "PrivacyDetector",
    "PrivacyEngine",
    "PrivacyTokenizer",
    "evaluate_item",
    "sanitize_text",
]
