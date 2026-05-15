"""Build script: generates build_info.py, then runs PyInstaller and packages the zip.

Build hash = first 7 chars of sha256(main.py + dds_decoder.py).
Build date = UTC timestamp at build time.
"""
import hashlib
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SOURCES = ["main.py", "dds_decoder.py"]


def compute_build_hash() -> str:
    # Prefer git short SHA; fall back to content hash if not a git repo.
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
        return sha + ("-dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        h = hashlib.sha256()
        for name in SOURCES:
            h.update((ROOT / name).read_bytes())
        return h.hexdigest()[:7]


def write_build_info(build_hash: str, build_date: str) -> None:
    (ROOT / "build_info.py").write_text(
        f'BUILD_HASH = "{build_hash}"\n'
        f'BUILD_DATE = "{build_date}"\n',
        encoding="utf-8",
    )


def run_pyinstaller() -> None:
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "EZDDSViewer.spec", "--noconfirm"],
        cwd=ROOT,
    )


def package_zip() -> Path:
    dist = ROOT / "dist"
    exe = dist / "EZDDSViewer.exe"
    readme = ROOT / "README.md"
    shutil.copy2(readme, dist / "README.md")
    zip_path = dist / "EZDDSViewer.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe, "EZDDSViewer.exe")
        zf.write(dist / "README.md", "README.md")
    return zip_path


def main() -> None:
    build_hash = compute_build_hash()
    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Build hash: {build_hash}")
    print(f"Build date: {build_date}")
    write_build_info(build_hash, build_date)
    run_pyinstaller()
    zip_path = package_zip()
    print(f"Packaged: {zip_path}")


if __name__ == "__main__":
    main()
