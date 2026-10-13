import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    region: str
    table: str
    uploads: str
    results: str
    queue_url: str
    max_bytes: int
    max_rows: int
    processing_seconds: int
    lease_seconds: int
    max_attempts: int

    @classmethod
    def load(cls) -> "Settings":
        def positive(name: str, default: int) -> int:
            value = int(os.getenv(name, str(default)))
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            return value

        return cls(
            os.getenv("AWS_REGION", "us-east-1"),
            os.environ["TABLE_NAME"],
            os.environ["UPLOAD_BUCKET"],
            os.environ["RESULT_BUCKET"],
            os.environ["QUEUE_URL"],
            positive("MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
            positive("MAX_ROWS", 100_000),
            positive("PROCESSING_SECONDS", 45),
            positive("LEASE_SECONDS", 120),
            positive("MAX_ATTEMPTS", 5),
        )
