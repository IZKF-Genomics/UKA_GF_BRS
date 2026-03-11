#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_DIR = "/data/raw/.archive_manifests"
DEFAULT_ALLOWED_ROOTS = "/data/raw"
DEFAULT_INSTRUMENTS = [
    "miseq1_M00818",
    "miseq2_M04404",
    "miseq3_M00403",
    "nextseq500_NB501289",
    "novaseq_A01742",
]
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _style(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _title(text: str) -> str:
    return _style(text, "1;36")


def _ok(text: str) -> str:
    return _style(text, "1;32")


def _warn(text: str) -> str:
    return _style(text, "1;33")


def _err(text: str) -> str:
    return _style(text, "1;31")


def _dim(text: str) -> str:
    return _style(text, "2")


def load_ctx() -> dict[str, Any]:
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _print_section(title: str) -> None:
    print("\n" + _title("=" * 80))
    print(_title(title))
    print(_title("=" * 80))


def _input_yes_no(prompt: str, default_yes: bool = False) -> bool:
    suffix = "Y/n" if default_yes else "y/N"
    answer = input(_title(f"{prompt} [{suffix}]: ")).strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}


def _acquire_lock(lock_path: Path) -> int:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd = os.open(str(lock_path), flags)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    return fd


def _release_lock(fd: int, lock_path: Path) -> None:
    os.close(fd)
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _resolve_latest_manifest(manifest_dir: Path) -> Path:
    candidates = sorted(manifest_dir.glob("archive_rawdata_*.json"))
    if not candidates:
        raise SystemExit(f"No archive_rawdata manifest found in {manifest_dir}")
    return candidates[-1]


def _is_under(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _is_safe_source_path(source_path: Path, allowed_roots: list[Path], allowed_instruments: set[str]) -> tuple[bool, str]:
    if not source_path.is_absolute():
        return False, "source path is not absolute"

    resolved = source_path.resolve(strict=False)
    for root in allowed_roots:
        if not _is_under(resolved, root):
            continue

        rel_parts = resolved.relative_to(root).parts
        if len(rel_parts) < 2:
            return False, "source path is too shallow (must include instrument/run folder)"
        instrument = rel_parts[0]
        if instrument not in allowed_instruments:
            return False, f"instrument not allowed: {instrument}"

        instrument_root = root / instrument
        if resolved == instrument_root:
            return False, "refusing to delete instrument root"
        if resolved == root:
            return False, "refusing to delete source root"
        if source_path.is_symlink() or resolved.is_symlink():
            return False, "refusing to delete symlink"
        return True, ""

    return False, "source path is outside allowed roots"


def _manifest_write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_params() -> dict[str, Any]:
    ctx = load_ctx()
    params = dict(ctx.get("params") or {})

    parser = argparse.ArgumentParser(description="Cleanup archived run folders from archive_rawdata manifest.")
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--allowed-source-roots", default=DEFAULT_ALLOWED_ROOTS)
    parser.add_argument("--instrument-folders", default=",".join(DEFAULT_INSTRUMENTS))
    parser.add_argument("--non-interactive", nargs="?", const="true", default="false")
    parser.add_argument("--interactive", nargs="?", const="true", default="true")
    parser.add_argument("--yes", nargs="?", const="true", default="false")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")

    if params:
        return params

    args = parser.parse_args()
    return {
        "manifest_path": args.manifest_path,
        "manifest_dir": args.manifest_dir,
        "allowed_source_roots": args.allowed_source_roots,
        "instrument_folders": args.instrument_folders,
        "non_interactive": args.non_interactive,
        "interactive": args.interactive,
        "yes": args.yes,
        "dry_run": args.dry_run,
    }


def main() -> None:
    params = _parse_params()

    manifest_path_raw = str(params.get("manifest_path") or "").strip()
    manifest_dir = Path(str(params.get("manifest_dir") or DEFAULT_MANIFEST_DIR)).expanduser().resolve()
    allowed_roots = [Path(p).expanduser().resolve() for p in _split_csv(params.get("allowed_source_roots") or DEFAULT_ALLOWED_ROOTS)]
    allowed_instruments = set(_split_csv(params.get("instrument_folders") or ",".join(DEFAULT_INSTRUMENTS)))
    non_interactive = _parse_bool(params.get("non_interactive"), False)
    interactive = _parse_bool(params.get("interactive"), True)
    yes = _parse_bool(params.get("yes"), False)
    dry_run = _parse_bool(params.get("dry_run"), False)

    if non_interactive:
        interactive = False
        yes = True
        print(_dim("[mode] non_interactive=true -> interactive disabled, global confirmation auto-approved"))

    if manifest_path_raw:
        manifest_path = Path(manifest_path_raw).expanduser().resolve()
    else:
        manifest_path = _resolve_latest_manifest(manifest_dir)

    if not manifest_path.exists() or not manifest_path.is_file():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list):
        raise SystemExit("Manifest has invalid format: missing list field 'records'")

    eligible_indexes: list[int] = []
    for i, rec in enumerate(records):
        status = str(rec.get("status") or "")
        copy_status = str(rec.get("copy_status") or "")
        verify_status = str(rec.get("verify_status") or "")
        cleanup_status = str(rec.get("cleanup_status") or "")
        if cleanup_status in {"done", "skipped_not_eligible", "skipped_outside_allowed_root", "skipped_missing"}:
            continue
        if status == "copied_verified" and copy_status == "ok" and verify_status == "ok":
            eligible_indexes.append(i)

    _print_section("archive_cleanup")
    print(f"Manifest: {manifest_path}")
    print(f"Allowed roots: {', '.join(str(p) for p in allowed_roots)}")
    print(f"Allowed instruments: {', '.join(sorted(allowed_instruments))}")
    print(f"Eligible runs: {len(eligible_indexes)}")
    if dry_run:
        print(_warn("Dry-run enabled: no source directories will be deleted."))

    if not eligible_indexes:
        print(_warn("No eligible runs found for cleanup."))
        return

    if not yes:
        if not (interactive and sys.stdin.isatty()):
            raise SystemExit("Global confirmation required. Re-run with --yes or interactive mode.")
        if not _input_yes_no("Proceed with cleanup for all eligible runs?", default_yes=False):
            raise SystemExit("Cancelled by user.")

    lock_path = Path("/tmp/archive_cleanup.lock")
    try:
        lock_fd = _acquire_lock(lock_path)
    except FileExistsError:
        raise SystemExit(f"Another archive_cleanup process is running (lock exists: {lock_path})")

    done = 0
    failed = 0
    skipped = 0

    try:
        cleanup_history = payload.get("cleanup_runs")
        if not isinstance(cleanup_history, list):
            cleanup_history = []
            payload["cleanup_runs"] = cleanup_history

        run_event: dict[str, Any] = {
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "manifest": str(manifest_path),
            "dry_run": dry_run,
            "deleted": 0,
            "failed": 0,
            "skipped": 0,
        }

        for idx in eligible_indexes:
            rec = records[idx]
            source_raw = str(rec.get("source") or "").strip()
            source_path = Path(source_raw)

            ok, reason = _is_safe_source_path(source_path, allowed_roots, allowed_instruments)
            if not ok:
                rec["cleanup_status"] = "skipped_not_eligible"
                rec["cleanup_error"] = reason
                skipped += 1
                continue

            resolved_source = source_path.resolve(strict=False)
            if not resolved_source.exists():
                rec["cleanup_status"] = "skipped_missing"
                rec["cleanup_error"] = "source path does not exist"
                skipped += 1
                continue
            if not resolved_source.is_dir():
                rec["cleanup_status"] = "skipped_not_eligible"
                rec["cleanup_error"] = "source path is not a directory"
                skipped += 1
                continue

            rec["cleanup_attempted_at"] = datetime.now().isoformat(timespec="seconds")
            if dry_run:
                rec["cleanup_status"] = "dry_run_only"
                rec["cleanup_error"] = ""
                print(_warn(f"[dry-run] Would remove: {resolved_source}"))
                skipped += 1
                continue

            print(_warn(f"[cleanup] Removing: {resolved_source}"))
            try:
                shutil.rmtree(resolved_source)
                rec["cleanup_status"] = "done"
                rec["cleanup_error"] = ""
                done += 1
            except Exception as exc:  # noqa: BLE001
                rec["cleanup_status"] = "failed"
                rec["cleanup_error"] = str(exc)
                failed += 1

            _manifest_write(manifest_path, payload)

        run_event["deleted"] = done
        run_event["failed"] = failed
        run_event["skipped"] = skipped
        run_event["finished_at"] = datetime.now().isoformat(timespec="seconds")
        cleanup_history.append(run_event)
        _manifest_write(manifest_path, payload)

        _print_section("Done")
        print(_ok(f"Manifest updated: {manifest_path}"))
        print(_ok(f"Deleted: {done}"))
        if failed:
            print(_err(f"Failed: {failed}"))
        else:
            print(_ok("Failed: 0"))
        print(_warn(f"Skipped: {skipped}"))

        if failed:
            raise SystemExit(1)
    finally:
        _release_lock(lock_fd, lock_path)


if __name__ == "__main__":
    main()
