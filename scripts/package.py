import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def archive(files: dict[str, Path], destination: Path) -> str:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, source in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, source.read_bytes())
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main() -> None:
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    requirements = output / "requirements.txt"
    subprocess.run(
        [
            "uv",
            "export",
            "--locked",
            "--no-dev",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    with tempfile.TemporaryDirectory(prefix="cloudforge-package-") as directory:
        deps = Path(directory)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--target",
                str(deps),
                "--python-platform",
                "x86_64-manylinux2014",
                "--python-version",
                "3.12",
                "--only-binary",
                ":all:",
                "-r",
                str(requirements),
            ],
            check=True,
        )
        hashes = {}
        for app in ("api", "worker"):
            files = {
                p.relative_to(deps).as_posix(): p
                for p in deps.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
            }
            for source, prefix in (
                (ROOT / "packages/shared", "shared"),
                (ROOT / f"apps/{app}", f"apps/{app}"),
            ):
                files.update(
                    {
                        f"{prefix}/{p.relative_to(source).as_posix()}": p
                        for p in source.rglob("*.py")
                    }
                )
            files["apps/__init__.py"] = ROOT / "apps/__init__.py"
            hashes[f"{app}.zip"] = archive(files, output / f"{app}.zip")
        (output / "checksums.sha256").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="utf-8"
        )
        (output / "manifest.json").write_text(
            json.dumps(
                {"runtime": "python3.12", "architecture": "x86_64", "artifacts": hashes}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps(hashes, indent=2))


if __name__ == "__main__":
    main()
