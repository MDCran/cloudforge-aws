import csv
import hashlib
import io
import math
import time
from typing import Any


class ProcessingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def process_csv(
    data: bytes,
    required: list[str],
    numeric: list[str],
    *,
    max_rows: int = 100_000,
    seconds: int = 45,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProcessingError("INVALID_ENCODING", "CSV must use UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        columns = next(reader, [])
        if not columns or len(columns) > 256 or len(set(columns)) != len(columns):
            raise ProcessingError("INVALID_HEADER", "CSV needs unique headers; maximum 256 columns")
        if any(not c.strip() or len(c) > 100 for c in columns):
            raise ProcessingError(
                "INVALID_HEADER", "Headers must be nonempty and at most 100 characters"
            )
        absent = set(required + numeric) - set(columns)
        if absent:
            raise ProcessingError("MISSING_COLUMNS", "CSV is missing configured columns")
        stats: dict[str, dict[str, Any]] = {
            c: {"missing": 0, "count": 0, "sum": 0.0, "min": None, "max": None} for c in columns
        }
        seen: set[bytes] = set()
        rows = duplicates = error_count = 0
        errors: list[dict[str, Any]] = []

        def error(row: int, column: str, code: str) -> None:
            nonlocal error_count
            error_count += 1
            if len(errors) < 100:
                errors.append({"row": row, "column": column, "code": code})

        for row in reader:
            rows += 1
            if rows > max_rows:
                raise ProcessingError("ROW_LIMIT", "CSV exceeds the record limit")
            if time.monotonic() - started > seconds:
                raise ProcessingError("PROCESSING_TIMEOUT", "Processing exceeded its time budget")
            if len(row) != len(columns):
                error(rows, "", "COLUMN_COUNT")
                continue
            fingerprint = hashlib.sha256(repr(row).encode()).digest()
            if fingerprint in seen:
                duplicates += 1
            seen.add(fingerprint)
            for column, raw in zip(columns, row, strict=True):
                value = raw.strip()
                entry = stats[column]
                if not value:
                    entry["missing"] += 1
                    if column in required:
                        error(rows, column, "REQUIRED_VALUE")
                    continue
                try:
                    number = float(value)
                    if not math.isfinite(number) or abs(number) > 1e100:
                        raise ValueError("Numeric value outside supported range")
                except ValueError:
                    if column in numeric:
                        error(rows, column, "INVALID_NUMBER")
                    continue
                entry["count"] += 1
                entry["sum"] += number
                entry["min"] = number if entry["min"] is None else min(entry["min"], number)
                entry["max"] = number if entry["max"] is None else max(entry["max"], number)
        return {
            "schema_version": 1,
            "row_count": rows,
            "column_count": len(columns),
            "duplicate_rows": duplicates,
            "validation_error_count": error_count,
            "validation_errors": errors,
            "errors_truncated": error_count > len(errors),
            "columns": [
                {
                    "name": c,
                    "missing_values": s["missing"],
                    "numeric": {
                        "count": s["count"],
                        "min": s["min"],
                        "max": s["max"],
                        "mean": s["sum"] / s["count"] if s["count"] else None,
                    },
                }
                for c, s in stats.items()
            ],
        }
    except csv.Error as exc:
        raise ProcessingError(
            "MALFORMED_CSV", "CSV contains invalid quoting or oversized fields"
        ) from exc
