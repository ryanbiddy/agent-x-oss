from __future__ import annotations


class XAutomationError(RuntimeError):
    """Base exception for X browser automation failures."""


class AuthenticationRequiredError(XAutomationError):
    """Raised when the session is not authenticated and login cannot complete."""


class RateLimitError(XAutomationError):
    """Raised when X rate-limits timeline or reply access."""


class DomChangedError(XAutomationError):
    """Raised when the expected X DOM structure is missing."""


class ReplyPostError(XAutomationError):
    """Raised when a reply could not be posted."""
