import pytest
from shared.models import JobInput

from apps.worker.processor import ProcessingError, process_csv


def test_report_statistics_and_validation() -> None:
    report = process_csv(b"name,amount\nAda,10\nAda,10\n,20\nBob,no\n", ["name"], ["amount"])
    assert report["row_count"] == 4
    assert report["duplicate_rows"] == 1
    assert report["validation_error_count"] == 2
    assert report["columns"][1]["numeric"]["mean"] == pytest.approx(40 / 3)
    assert report["columns"][0]["missing_values"] == 1


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"", "INVALID_HEADER"),
        (b"x,x\n1,2", "INVALID_HEADER"),
        (b"x\n\xff", "INVALID_ENCODING"),
        (b'x\n"broken', "MALFORMED_CSV"),
        (b" \n1", "INVALID_HEADER"),
    ],
)
def test_bad_csv(data: bytes, code: str) -> None:
    with pytest.raises(ProcessingError) as exc:
        process_csv(data, [], [])
    assert exc.value.code == code


def test_limits_and_error_sampling() -> None:
    with pytest.raises(ProcessingError, match="record limit"):
        process_csv(b"x\n1\n2", [], [], max_rows=1)
    with pytest.raises(ProcessingError, match="missing"):
        process_csv(b"x\n1", ["absent"], [])
    report = process_csv(b"x\n" + b"no\n" * 150, [], ["x"])
    assert report["validation_error_count"] == 150
    assert len(report["validation_errors"]) == 100
    assert report["errors_truncated"]


def test_nonfinite_numbers_and_utf8_bom() -> None:
    report = process_csv(b"\xef\xbb\xbfx\nNaN\ninf\n1e200\n5\n", [], ["x"])
    assert report["validation_error_count"] == 3
    assert report["columns"][0]["numeric"]["mean"] == 5


@pytest.mark.parametrize("filename", ["../x.csv", "/x.csv", "x\\y.csv", "x.exe", ".csv"])
def test_unsafe_filenames(filename: str) -> None:
    with pytest.raises(ValueError):
        JobInput(name="Test", filename=filename, size=2)
