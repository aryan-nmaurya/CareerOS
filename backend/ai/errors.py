class AIUnavailable(Exception):
    """The AI provider could not be reached after retries were exhausted,
    or returned a non-retryable error."""


class AIInvalidResponse(Exception):
    """The AI provider returned a response that failed schema or shape
    validation."""
