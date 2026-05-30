"""Service-layer exceptions."""


class PreferenceValidationError(ValueError):
    """Raised when user preferences fail validation."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        message = "; ".join(f"{field}: {msg}" for field, msg in errors.items())
        super().__init__(message)
