"""Data layer exceptions."""


class DatasetNotFoundError(FileNotFoundError):
    """Raised when the restaurant SQLite database is missing or empty."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(
            f"Restaurant database not found at '{path}'. "
            "Run dataset ingestion first: python scripts/ingest_dataset.py"
        )
