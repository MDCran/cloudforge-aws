import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cloudforge-lambda-") as directory:
        for archive, module in (
            ("api.zip", "apps.api.handler"),
            ("worker.zip", "apps.worker.handler"),
        ):
            destination = Path(directory) / archive.removesuffix(".zip")
            destination.mkdir()
            with zipfile.ZipFile(ROOT / "artifacts" / archive) as bundle:
                bundle.extractall(destination)
            environment = {**os.environ, "PYTHONPATH": str(destination)}
            subprocess.run(
                [sys.executable, "-S", "-c", f"import {module}"],
                cwd=directory,
                env=environment,
                check=True,
            )
    print("Both Lambda deployment packages import successfully.")


if __name__ == "__main__":
    main()
