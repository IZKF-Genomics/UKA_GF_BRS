#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[1]
if str(WORKFLOWS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOWS_DIR))

from archive_common import (
    current_user as _shared_current_user,
    load_active_keep_runs as _shared_load_active_keep_runs,
    load_rules as _shared_load_rules,
    save_rules as _shared_save_rules,
    validate_keep_until as _shared_validate_keep_until,
)

DEFAULT_SOURCE_ROOT = "/data/raw"
DEFAULT_TARGET_ROOT = "/mnt/nextgen2/archive/raw"
DEFAULT_RETENTION_DAYS = 90
DEFAULT_MANIFEST_DIR = "/data/shared/bpm_manifests"
DEFAULT_KEEP_RULES_PATH = "/data/shared/bpm_manifests/keep_rules.yaml"
DEFAULT_INSTRUMENTS = [
    "miseq1_M00818",
    "miseq2_M04404",
    "miseq3_M00403",
    "nextseq500_NB501289",
    "novaseq_A01742",
]
RUN_PREFIX_RE = re.compile(r"^(?P<prefix>\d{6})_")
USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _workflow_public_id() -> str:
    workflow_id = str(os.environ.get("BPM_WORKFLOW_ID") or "archive_rawdata").strip()
    return workflow_id or "archive_rawdata"


def _workflow_label() -> str:
    return "archive_raw" if _workflow_public_id() == "archive_raw" else "archive_rawdata"


def _workflow_manifest_prefix() -> str:
    return "archive_raw" if _workflow_public_id() == "archive_raw" else "archive_rawdata"


def _workflow_lock_path() -> Path:
    # Keep one shared lock for both archive_raw and archive_rawdata aliases.
    return Path("/tmp/archive_raw.lock")


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


def _cmd(text: str) -> str:
    return _style(text, "36")


def _dim(text: str) -> str:
    return _style(text, "2")


@dataclass
class RunCandidate:
    instrument: str
    run_id: str
    owner_user: str
    run_date: date
    retention_reference_date: date
    retention_reference_source: str
    source_path: Path
    target_instrument_path: Path
    target_run_path: Path
    size_bytes: int
    kept_by_rule: bool = False


def load_ctx() -> dict[str, Any]:
    ctx_path = os.environ.get("BPM_CTX_PATH")
    if not ctx_path or not Path(ctx_path).is_file():
        return {}
    with open(ctx_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


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


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


def _format_bytes(num_bytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def _parse_run_date(run_id: str) -> date | None:
    match = RUN_PREFIX_RE.match(run_id)
    if not match:
        return None
    prefix = match.group("prefix")
    try:
        yy = int(prefix[0:2])
        mm = int(prefix[2:4])
        dd = int(prefix[4:6])
        return date(2000 + yy, mm, dd)
    except ValueError:
        return None


def _parse_exported_at_date(value: Any) -> date | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def _load_active_keep_runs(keep_rules_path: Path) -> tuple[set[str], list[str]]:
    if not keep_rules_path.exists():
        return set(), []
    try:
        payload = yaml.safe_load(keep_rules_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return set(), [f"Failed to parse keep_rules file {keep_rules_path}: {exc}"]
    if not isinstance(payload, dict):
        return set(), [f"Invalid keep_rules format in {keep_rules_path}: expected mapping"]

    runs = payload.get("runs") or {}
    if not isinstance(runs, dict):
        return set(), [f"Invalid keep_rules.runs format in {keep_rules_path}: expected mapping"]

    today = date.today()
    active: set[str] = set()
    notes: list[str] = []
    for run_id, rec in runs.items():
        run_id_s = str(run_id).strip()
        if not run_id_s:
            continue
        if not isinstance(rec, dict):
            notes.append(f"Invalid keep_rules record for run_id={run_id_s}: expected mapping")
            continue
        if rec.get("keep", True) is False:
            continue
        keep_until_raw = rec.get("keep_until")
        if keep_until_raw in (None, ""):
            active.add(run_id_s)
            continue
        try:
            keep_until = date.fromisoformat(str(keep_until_raw))
        except ValueError:
            notes.append(f"Invalid keep_until in keep_rules for run_id={run_id_s}: {keep_until_raw}")
            active.add(run_id_s)
            continue
        if keep_until >= today:
            active.add(run_id_s)
    return active, notes


def _get_retention_reference(run_dir: Path, run_date: date) -> tuple[date, str]:
    meta_path = run_dir / "bpm.meta.yaml"
    if not meta_path.exists():
        return run_date, "run_name_prefix"
    try:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return run_date, "run_name_prefix"

    export = meta.get("export") or {}
    for key_path in (
        ("last_exported_at",),
        ("demux", "last_exported_at"),
    ):
        cur: Any = export
        for key in key_path:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(key)
        parsed = _parse_exported_at_date(cur)
        if parsed is not None:
            return parsed, "export_last_exported_at"

    return run_date, "run_name_prefix"


def _du_size_bytes(path: Path) -> int:
    result = subprocess.run(
        ["du", "-sb", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    first = result.stdout.strip().split()[0]
    return int(first)


def _compute_cutoff(retention_days: int) -> date:
    return date.today() - timedelta(days=retention_days)


def _owner_user(path: Path) -> str:
    try:
        uid = path.stat().st_uid
        return pwd.getpwuid(uid).pw_name
    except Exception:  # noqa: BLE001
        return "unknown"


def _discover_candidates(
    source_root: Path,
    target_root: Path,
    instruments: list[str],
    retention_days: int,
    skip_runs: set[str],
    keep_run_ids: set[str],
) -> tuple[list[RunCandidate], list[str]]:
    issues: list[str] = []
    cutoff = _compute_cutoff(retention_days)
    candidates: list[RunCandidate] = []

    for instrument in instruments:
        src_instrument = source_root / instrument
        dst_instrument = target_root / instrument

        if not src_instrument.exists() or not src_instrument.is_dir():
            issues.append(f"Missing source instrument directory: {src_instrument}")
            continue

        for entry in sorted(src_instrument.iterdir()):
            if not entry.is_dir():
                continue
            run_date = _parse_run_date(entry.name)
            if run_date is None:
                continue
            ref_date, ref_source = _get_retention_reference(entry, run_date)
            if ref_date >= cutoff:
                continue
            if entry.name in skip_runs:
                continue
            try:
                kept_by_rule = entry.name in keep_run_ids
                size_bytes = _du_size_bytes(entry)
            except Exception as exc:  # noqa: BLE001
                issues.append(f"Failed to calculate size for {entry}: {exc}")
                continue

            candidates.append(
                RunCandidate(
                    instrument=instrument,
                    run_id=entry.name,
                    owner_user=_owner_user(entry),
                    run_date=run_date,
                    retention_reference_date=ref_date,
                    retention_reference_source=ref_source,
                    source_path=entry,
                    target_instrument_path=dst_instrument,
                    target_run_path=dst_instrument / entry.name,
                    size_bytes=size_bytes,
                    kept_by_rule=kept_by_rule,
                )
            )

    candidates.sort(key=lambda c: (c.instrument, c.run_date, c.run_id))
    return candidates, issues


def _print_section(title: str) -> None:
    print("\n" + _title("=" * 80))
    print(_title(title))
    print(_title("=" * 80))


def _run_archive_tui(candidates: list[RunCandidate], rules_path: Path) -> bool:
    import curses

    if not candidates:
        return False

    payload = _shared_load_rules(rules_path)
    run_ids = [c.run_id for c in candidates]
    existing = payload.get("runs") or {}
    marked = {run_id: bool((existing.get(run_id) or {}).get("keep", False)) for run_id in run_ids}
    keep_until = {run_id: (existing.get(run_id) or {}).get("keep_until") for run_id in run_ids}
    set_by_map = {run_id: str((existing.get(run_id) or {}).get("set_by") or "-") for run_id in run_ids}

    def _column_width(values: list[str], header: str, min_width: int = 0, max_width: int | None = None) -> int:
        width = max([len(header), min_width, *(len(v) for v in values)], default=len(header))
        if max_width is not None:
            width = min(width, max_width)
        return width

    def _clip(value: str, width: int) -> str:
        if width <= 0:
            return ""
        if len(value) <= width:
            return value
        if width == 1:
            return value[:1]
        return value[: width - 1] + "~"

    def _save() -> int:
        changed = 0
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        user = _shared_current_user()
        runs = payload.setdefault("runs", {})
        for candidate in candidates:
            old = runs.get(candidate.run_id)
            if marked.get(candidate.run_id, False):
                rec = {
                    "keep": True,
                    "set_by": user,
                    "set_at": stamp,
                    "keep_until": keep_until.get(candidate.run_id) or None,
                }
                if old != rec:
                    runs[candidate.run_id] = rec
                    changed += 1
            elif candidate.run_id in runs:
                del runs[candidate.run_id]
                changed += 1
        _shared_save_rules(rules_path, payload)
        return changed

    def _curses_main(stdscr) -> tuple[bool, int]:
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.keypad(True)
        color_header = curses.A_BOLD
        color_help = curses.A_DIM
        color_row = curses.A_NORMAL
        color_marked = curses.A_BOLD
        color_selected = curses.A_REVERSE | curses.A_BOLD
        color_status = curses.A_BOLD
        color_summary = curses.A_DIM
        if curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                curses.init_pair(2, curses.COLOR_WHITE, -1)
                curses.init_pair(3, curses.COLOR_GREEN, -1)
                curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)
                curses.init_pair(5, curses.COLOR_YELLOW, -1)
                color_header = curses.color_pair(1) | curses.A_BOLD
                color_help = curses.color_pair(2) | curses.A_DIM
                color_row = curses.color_pair(2)
                color_marked = curses.color_pair(3) | curses.A_BOLD
                color_selected = curses.color_pair(4) | curses.A_BOLD
                color_status = curses.color_pair(5) | curses.A_BOLD
                color_summary = curses.color_pair(2) | curses.A_DIM
            except curses.error:
                pass

        idx = 0
        top = 0
        changed = False
        owner_values = [c.owner_user for c in candidates]
        inst_values = [c.instrument for c in candidates]
        set_by_values = [set_by_map.get(c.run_id, "-") for c in candidates]

        def _prompt_keep_until(current: str | None) -> str | None:
            h, w = stdscr.getmaxyx()
            prompt = "keep_until for selected run (YYYY-MM-DD, empty clears)"
            while True:
                curses.curs_set(1)
                stdscr.move(h - 2, 0)
                stdscr.clrtoeol()
                stdscr.addnstr(h - 2, 0, prompt, w - 1)
                stdscr.move(h - 1, 0)
                stdscr.clrtoeol()
                prefix = f"current={current} -> " if current else ""
                if prefix:
                    stdscr.addnstr(h - 1, 0, prefix, w - 1)
                stdscr.refresh()
                curses.echo()
                raw = stdscr.getstr(h - 1, min(len(prefix), max(0, w - 2)), max(1, w - len(prefix) - 1))
                curses.noecho()
                try:
                    return _shared_validate_keep_until(raw.decode("utf-8", errors="ignore").strip())
                except SystemExit:
                    stdscr.move(h - 1, 0)
                    stdscr.clrtoeol()
                    stdscr.addnstr(h - 1, 0, "Invalid date. Use YYYY-MM-DD.", w - 1, curses.A_BOLD)
                    stdscr.refresh()
                    curses.napms(900)
                finally:
                    curses.curs_set(0)

        def _render(status: str = "") -> None:
            nonlocal top
            h, w = stdscr.getmaxyx()
            stdscr.erase()
            stdscr.addnstr(0, 0, f"{_workflow_label()} | archive candidates | runs={len(candidates)}".ljust(max(0, w - 1)), w - 1, color_header)
            stdscr.addnstr(1, 0, "Only runs older than retention are shown. k: keep/unkeep  u: keep-until  s: save+continue  q: continue".ljust(max(0, w - 1)), w - 1, color_help)
            list_top = 4
            list_h = max(1, h - 6)
            inst_col = _column_width(inst_values, "Instrument", min_width=10, max_width=24)
            run_col = _column_width(run_ids, "Run ID", min_width=18, max_width=36)
            owner_col = _column_width(owner_values, "Owner", min_width=5, max_width=12)
            set_by_col = _column_width(set_by_values, "Set By", min_width=6, max_width=12)
            row_fmt = f"{{keep:<4}} {{archive:<7}} {{inst:<{inst_col}}} {{run:<{run_col}}} {{owner:<{owner_col}}} {{ku:<10}} {{set_by:<{set_by_col}}} {{size:>10}}"
            header = row_fmt.format(keep="Keep", archive="Archive", inst="Instrument", run="Run ID", owner="Owner", ku="Keep Until", set_by="Set By", size="Size")
            stdscr.addnstr(3, 0, header.ljust(max(0, w - 1)), w - 1, color_help | curses.A_BOLD)
            if idx < top:
                top = idx
            elif idx >= top + list_h:
                top = idx - list_h + 1
            for row in range(list_h):
                pos = top + row
                y = list_top + row
                if pos >= len(candidates):
                    stdscr.addnstr(y, 0, " " * max(0, w - 1), w - 1, color_row)
                    continue
                item = candidates[pos]
                line = row_fmt.format(
                    keep='yes' if marked.get(item.run_id, False) else 'no',
                    archive='no' if marked.get(item.run_id, False) else 'yes',
                    inst=_clip(item.instrument, inst_col),
                    run=_clip(item.run_id, run_col),
                    owner=_clip(item.owner_user, owner_col),
                    ku=(keep_until.get(item.run_id) or '-'),
                    set_by=_clip(set_by_map.get(item.run_id, '-'), set_by_col),
                    size=_format_bytes(item.size_bytes),
                )
                attr = color_selected if pos == idx else (color_marked if marked.get(item.run_id, False) else color_row)
                stdscr.addnstr(y, 0, line.ljust(max(0, w - 1)), w - 1, attr)
            selected_count = sum(1 for c in candidates if not marked.get(c.run_id, False))
            kept_count = len(candidates) - selected_count
            stdscr.addnstr(h - 2, 0, f"Will archive: {selected_count}  Kept: {kept_count}  Unsaved changes: {'yes' if changed else 'no'}".ljust(max(0, w - 1)), w - 1, color_summary)
            stdscr.addnstr(h - 1, 0, status.ljust(max(0, w - 1)), w - 1, color_status if status else color_row)
            stdscr.refresh()

        _render()
        while True:
            key = stdscr.getch()
            if key == curses.KEY_UP:
                idx = max(0, idx - 1)
                _render()
            elif key in (curses.KEY_DOWN, ord('j')):
                idx = min(len(candidates) - 1, idx + 1)
                _render()
            elif key in (ord('k'), ord(' ')):
                item = candidates[idx]
                marked[item.run_id] = not marked.get(item.run_id, False)
                changed = True
                _render()
            elif key == ord('u'):
                item = candidates[idx]
                keep_until[item.run_id] = _prompt_keep_until(keep_until.get(item.run_id))
                if keep_until[item.run_id] is not None:
                    marked[item.run_id] = True
                changed = True
                _render('keep_until updated')
            elif key == ord('s'):
                saved_changes = _save()
                _render(f'Saved keep changes: {saved_changes}. Continuing...')
                curses.napms(700)
                return True, saved_changes
            elif key == ord('q'):
                if changed:
                    _render('Unsaved changes. Press q again to discard and continue.')
                    if stdscr.getch() == ord('q'):
                        return False, 0
                    _render()
                    continue
                return False, 0

    saved, _ = curses.wrapper(_curses_main)
    return saved


def _print_plan(candidates: list[RunCandidate], retention_days: int, skip_runs: set[str], keep_run_ids: set[str]) -> None:
    cutoff = _compute_cutoff(retention_days)
    _print_section("Archive Plan")
    print(f"Retention days: {retention_days}")
    print(f"Archive runs older than: {cutoff.isoformat()} (strictly before this date)")
    print("Retention reference: export.last_exported_at -> run-name YYMMDD prefix")
    print(f"Runs skipped by user: {', '.join(sorted(skip_runs)) if skip_runs else '(none)'}")
    print(f"Runs protected by keep_rules: {len(keep_run_ids)}")

    if not candidates:
        print("\nNo run directories match the archive criteria.")
        return

    print("\nSelected runs:")
    run_col = max(32, min(50, max(len(c.run_id) for c in candidates) + 2))
    owner_col = max(8, min(14, max(len(c.owner_user) for c in candidates) + 2))
    status_col = 20
    row_fmt = f"{{no:>4}}  {{inst:<24}} {{run:<{run_col}}}{{owner:<{owner_col}}}{{status:<{status_col}}}{{size:>12}}"
    header = row_fmt.format(no="No.", inst="Instrument", run="Run ID", owner="Owner", status="Status", size="Size")
    print(_dim(header))
    print(_dim("-" * len(header)))
    for idx, item in enumerate(candidates, start=1):
        print(
            row_fmt.format(
                no=f"{idx}.",
                inst=item.instrument,
                run=item.run_id,
                owner=item.owner_user,
                status="kept (not archived)" if item.kept_by_rule else "selected",
                size=_format_bytes(item.size_bytes),
            )
        )

    selected = [c for c in candidates if not c.kept_by_rule]
    kept = [c for c in candidates if c.kept_by_rule]
    total = sum(c.size_bytes for c in selected)
    print("\nSummary:")
    print(_ok(f"- Selected run count: {len(selected)}"))
    print(_warn(f"- Kept run count: {len(kept)}"))
    print(_ok(f"- Total size: {_format_bytes(total)}"))


def _input_with_default(prompt: str, default: str) -> str:
    answer = input(_title(f"{prompt} [{default}]: ")).strip()
    return answer or default


def _input_yes_no(prompt: str, default_yes: bool = False) -> bool:
    suffix = "Y/n" if default_yes else "y/N"
    answer = input(_title(f"{prompt} [{suffix}]: ")).strip().lower()
    if not answer:
        return default_yes
    return answer in {"y", "yes"}


def _interactive_overrides(
    source_root: str,
    target_root: str,
    retention_days: int,
    instruments: list[str],
    skip_runs: set[str],
) -> tuple[str, str, int, list[str], set[str]]:
    _print_section(f"{_workflow_label()} Interactive Setup")
    print(_dim("Press Enter to keep defaults."))

    source_root = _input_with_default("Source root", source_root)
    target_root = _input_with_default("Target root", target_root)

    retention_raw = _input_with_default("Retention days", str(retention_days))
    try:
        retention_days = int(retention_raw)
    except ValueError:
        raise SystemExit(f"Invalid retention days: {retention_raw}")

    inst_default = ",".join(instruments)
    inst_raw = _input_with_default("Instrument folders (comma-separated)", inst_default)
    instruments = [v for v in _split_csv(inst_raw) if v]
    if not instruments:
        raise SystemExit("No instrument folders provided.")

    skip_default = ",".join(sorted(skip_runs))
    skip_raw = _input_with_default("Skip run IDs (comma-separated; optional)", skip_default)
    skip_runs = set(_split_csv(skip_raw))

    return source_root, target_root, retention_days, instruments, skip_runs


def _prompt_additional_skips(candidates: list[RunCandidate], skip_runs: set[str]) -> tuple[set[str], bool]:
    if not candidates:
        return skip_runs, False
    print("\n" + _title("Optional: enter additional run IDs to skip from this plan."))
    entered = input(_title("Additional skips (comma-separated, or Enter for none): ")).strip()
    if not entered:
        return skip_runs, False

    planned_ids = {c.run_id for c in candidates}
    changed = False
    for run_id in _split_csv(entered):
        if run_id in planned_ids:
            before = len(skip_runs)
            skip_runs.add(run_id)
            if len(skip_runs) != before:
                changed = True
        else:
            print(_warn(f"[warning] Run ID not in current plan, ignored: {run_id}"))
    return skip_runs, changed


def _ensure_target_free_space(target_root: Path, required_bytes: int, min_free_gb: int) -> None:
    usage = shutil.disk_usage(target_root)
    free_bytes = usage.free
    min_free_bytes = min_free_gb * 1024 * 1024 * 1024
    if free_bytes < min_free_bytes:
        raise SystemExit(
            f"Insufficient free space on {target_root}: {_format_bytes(free_bytes)} free, "
            f"requires at least {_format_bytes(min_free_bytes)}"
        )
    if required_bytes > free_bytes:
        raise SystemExit(
            f"Insufficient free space on {target_root}: need {_format_bytes(required_bytes)}, "
            f"but only {_format_bytes(free_bytes)} free"
        )


def _assert_writable_dir(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"Target directory missing or not a directory: {path}")
    if not os.access(path, os.W_OK | os.X_OK):
        raise SystemExit(f"No write permission for target directory: {path}")
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{_workflow_manifest_prefix()}_write_test_", dir=path, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Cannot write to target directory {path}: {exc}") from exc


def _preflight_target_paths(target_root: Path, candidates: list[RunCandidate]) -> None:
    _assert_writable_dir(target_root)
    seen: set[Path] = set()
    for candidate in candidates:
        instrument_dir = candidate.target_instrument_path
        if instrument_dir in seen:
            continue
        if not instrument_dir.exists():
            try:
                instrument_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                raise SystemExit(f"Failed to create target instrument directory {instrument_dir}: {exc}") from exc
        _assert_writable_dir(instrument_dir)
        seen.add(instrument_dir)


def _run_cmd(cmd: list[str]) -> None:
    print(_cmd("+ " + " ".join(cmd)))
    subprocess.run(cmd, check=True)


def _rsync_copy(candidate: RunCandidate) -> None:
    candidate.target_instrument_path.mkdir(parents=True, exist_ok=True)
    _run_cmd(
        [
            "rsync",
            "-a",
            "--human-readable",
            "--info=progress2",
            "--no-inc-recursive",
            "--partial",
            str(candidate.source_path),
            str(candidate.target_instrument_path),
        ]
    )


def _rsync_verify(candidate: RunCandidate) -> None:
    verify = subprocess.run(
        [
            "rsync",
            "-avhn",
            "--delete",
            f"{candidate.source_path}/",
            f"{candidate.target_run_path}/",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    lines = [line for line in verify.stdout.splitlines() if line.strip()]
    payload_lines = [line for line in lines if not line.startswith(("sending ", "sent ", "total size is "))]
    if payload_lines:
        raise RuntimeError(
            "Verification mismatch after copy for "
            f"{candidate.run_id}. rsync dry-run reported differences."
        )


def _acquire_lock(lock_path: Path) -> int:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags)
    except FileExistsError:
        try:
            raw = lock_path.read_text(encoding="utf-8").strip()
            pid = int(raw)
        except Exception:
            pid = None
        if pid is not None:
            try:
                os.kill(pid, 0)
            except OSError:
                lock_path.unlink(missing_ok=True)
                fd = os.open(str(lock_path), flags)
            else:
                raise
        else:
            lock_path.unlink(missing_ok=True)
            fd = os.open(str(lock_path), flags)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    return fd


def _release_lock(fd: int, lock_path: Path) -> None:
    os.close(fd)
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _append_log(log_path: Path, message: str) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {message}\n")


def _manifest_setup_hint(dir_path: Path) -> str:
    return (
        f"Manifest/log directory is not writable: {dir_path}\n"
        "Choose one of:\n"
        f"1) Create and grant access:\n"
        f"   sudo mkdir -p {dir_path}\n"
        f"   sudo chown root:bioinfo {dir_path}\n"
        f"   sudo chmod 2775 {dir_path}\n"
        "2) Use another writable location:\n"
        "   --manifest-dir /data/shared/bpm_manifests\n"
        "   or --manifest-path /data/shared/bpm_manifests/<name>.json"
    )


def _preflight_manifest_paths(manifest_path: Path, log_path: Path) -> None:
    for dir_path in (manifest_path.parent, log_path.parent):
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(_manifest_setup_hint(dir_path) + f"\nDetail: {exc}") from exc

        if not os.access(dir_path, os.W_OK | os.X_OK):
            raise SystemExit(_manifest_setup_hint(dir_path))

    try:
        with tempfile.NamedTemporaryFile(prefix=".archive_manifest_write_test_", dir=manifest_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(manifest_path.parent) + f"\nDetail: {exc}") from exc

    try:
        with tempfile.NamedTemporaryFile(prefix=".archive_log_write_test_", dir=log_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(log_path.parent) + f"\nDetail: {exc}") from exc


def _manifest_payload(metadata: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **metadata,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "records": records,
    }


def _write_manifest(manifest_path: Path, metadata: dict[str, Any], records: list[dict[str, Any]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(_manifest_payload(metadata, records), indent=2),
        encoding="utf-8",
    )


def _parse_params() -> dict[str, Any]:
    ctx = load_ctx()
    params = dict(ctx.get("params") or {})

    parser = argparse.ArgumentParser(description="Archive old raw sequencing run folders with rsync.")
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--target-root", default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--instrument-folders", default=",".join(DEFAULT_INSTRUMENTS))
    parser.add_argument("--skip-runs", default="")
    parser.add_argument("--non-interactive", nargs="?", const="true", default="false")
    parser.add_argument("--interactive", nargs="?", const="true", default="true")
    parser.add_argument("--yes", nargs="?", const="true", default="false")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")
    parser.add_argument("--cleanup", nargs="?", const="true", default="false")
    parser.add_argument("--min-free-gb", type=int, default=500)
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--keep-rules-path", default=DEFAULT_KEEP_RULES_PATH)
    parser.add_argument("--tui", nargs="?", const="true", default="true")

    if params:
        return params

    args = parser.parse_args()
    return {
        "source_root": args.source_root,
        "target_root": args.target_root,
        "retention_days": args.retention_days,
        "instrument_folders": args.instrument_folders,
        "skip_runs": args.skip_runs,
        "non_interactive": args.non_interactive,
        "interactive": args.interactive,
        "yes": args.yes,
        "dry_run": args.dry_run,
        "cleanup": args.cleanup,
        "min_free_gb": args.min_free_gb,
        "manifest_path": args.manifest_path,
        "manifest_dir": args.manifest_dir,
        "keep_rules_path": args.keep_rules_path,
        "tui": args.tui,
    }


def main() -> None:
    params = _parse_params()

    source_root = str(params.get("source_root") or DEFAULT_SOURCE_ROOT).strip()
    target_root = str(params.get("target_root") or DEFAULT_TARGET_ROOT).strip()
    retention_days = _parse_int(params.get("retention_days"), DEFAULT_RETENTION_DAYS)
    instruments = _split_csv(params.get("instrument_folders") or ",".join(DEFAULT_INSTRUMENTS))
    if not instruments:
        instruments = list(DEFAULT_INSTRUMENTS)

    skip_runs = set(_split_csv(params.get("skip_runs")))
    non_interactive = _parse_bool(params.get("non_interactive"), False)
    interactive = _parse_bool(params.get("interactive"), True)
    dry_run = _parse_bool(params.get("dry_run"), False)
    cleanup_requested = _parse_bool(params.get("cleanup"), False)
    yes = _parse_bool(params.get("yes"), False)
    min_free_gb = _parse_int(params.get("min_free_gb"), 500)
    manifest_path_raw = str(params.get("manifest_path") or "").strip()
    manifest_dir = Path(str(params.get("manifest_dir") or DEFAULT_MANIFEST_DIR)).expanduser().resolve()
    keep_rules_path = Path(str(params.get("keep_rules_path") or DEFAULT_KEEP_RULES_PATH)).expanduser().resolve()
    tui = _parse_bool(params.get("tui"), True)

    if retention_days < 0:
        raise SystemExit("retention_days must be >= 0")

    if cleanup_requested:
        print(_warn(f"[warning] cleanup in {_workflow_label()} is deprecated and ignored. Use archive_cleanup workflow."))

    if non_interactive:
        interactive = False
        yes = True
        print(_dim("[mode] non_interactive=true -> interactive disabled, global confirmation auto-approved"))

    if interactive and sys.stdin.isatty():
        source_root, target_root, retention_days, instruments, skip_runs = _interactive_overrides(
            source_root,
            target_root,
            retention_days,
            instruments,
            skip_runs,
        )

    source_root_path = Path(source_root).expanduser().resolve()
    target_root_path = Path(target_root).expanduser().resolve()

    if not source_root_path.exists() or not source_root_path.is_dir():
        raise SystemExit(f"Source root not found or not a directory: {source_root_path}")
    if not target_root_path.exists() or not target_root_path.is_dir():
        raise SystemExit(f"Target root not found or not a directory: {target_root_path}")
    keep_run_ids, keep_notes = _shared_load_active_keep_runs(keep_rules_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_manifest_path = manifest_dir / f"{_workflow_manifest_prefix()}_{timestamp}.json"
    manifest_path = Path(manifest_path_raw).expanduser().resolve() if manifest_path_raw else default_manifest_path
    log_path = manifest_path.parent / f"{manifest_path.stem}.log"

    _print_section("Path Confirmation")
    print(f"Source root: {source_root_path}")
    print(f"Target root: {target_root_path}")
    print(f"Instrument folders: {', '.join(instruments)}")
    print(f"Keep rules path: {keep_rules_path}")
    print(f"Protected runs from keep rules: {len(keep_run_ids)}")
    print(f"Manifest path: {manifest_path}")
    print(f"Log path: {log_path}")

    # Fail fast before expensive discovery/copy if manifest/log location is not writable.
    _preflight_manifest_paths(manifest_path, log_path)

    candidates, issues = _discover_candidates(
        source_root=source_root_path,
        target_root=target_root_path,
        instruments=instruments,
        retention_days=retention_days,
        skip_runs=skip_runs,
        keep_run_ids=keep_run_ids,
    )

    if issues or keep_notes:
        _print_section("Discovery Notes")
        for issue in issues:
            print(_warn(f"- {issue}"))
        for note in keep_notes:
            print(_warn(f"- {note}"))

    if interactive and sys.stdin.isatty() and tui and candidates:
        _run_archive_tui(candidates, keep_rules_path)
        keep_run_ids, keep_notes = _shared_load_active_keep_runs(keep_rules_path)
        candidates, issues = _discover_candidates(
            source_root=source_root_path,
            target_root=target_root_path,
            instruments=instruments,
            retention_days=retention_days,
            skip_runs=skip_runs,
            keep_run_ids=keep_run_ids,
        )
        if issues or keep_notes:
            _print_section("Discovery Notes")
            for issue in issues:
                print(_warn(f"- {issue}"))
            for note in keep_notes:
                print(_warn(f"- {note}"))
        _print_section("Archive Summary")
        print(f"Retention days: {retention_days}")
        print(f"Archive runs older than: {_compute_cutoff(retention_days).isoformat()} (strictly before this date)")
        print(f"Runs protected by keep_rules: {len(keep_run_ids)}")
        selected_candidates = [c for c in candidates if not c.kept_by_rule]
        kept_candidates = [c for c in candidates if c.kept_by_rule]
        print(_ok(f"Selected run count: {len(selected_candidates)}"))
        print(_warn(f"Kept run count: {len(kept_candidates)}"))
        print(_ok(f"Total size to archive: {_format_bytes(sum(c.size_bytes for c in selected_candidates))}"))
    else:
        _print_plan(candidates, retention_days, skip_runs, keep_run_ids)

    selected_candidates = [c for c in candidates if not c.kept_by_rule]

    if not selected_candidates:
        print(_warn("\nNothing to archive. Exiting."))
        return

    if not yes:
        if not (interactive and sys.stdin.isatty()):
            raise SystemExit("Global confirmation required. Re-run with --yes or interactive mode.")
        if not _input_yes_no("Proceed with archive/copy/verify sequence for all selected runs?", default_yes=False):
            raise SystemExit("Cancelled by user.")

    lock_path = _workflow_lock_path()
    try:
        lock_fd = _acquire_lock(lock_path)
    except FileExistsError:
        raise SystemExit(f"Another {_workflow_label()} process is running (lock exists: {lock_path})")

    metadata: dict[str, Any] = {
        "workflow_id": _workflow_public_id(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root_path),
        "target_root": str(target_root_path),
        "retention_days": retention_days,
        "instrument_folders": instruments,
        "skip_runs": sorted(skip_runs),
        "keep_rules_path": str(keep_rules_path),
        "keep_protected_runs": sorted(keep_run_ids),
        "dry_run": dry_run,
        "cleanup_in_archive": False,
        "log_path": str(log_path),
    }

    records: list[dict[str, Any]] = []
    copy_failures = 0
    verify_failures = 0

    try:
        required = sum(c.size_bytes for c in selected_candidates)
        _ensure_target_free_space(target_root_path, required, min_free_gb)
        _preflight_target_paths(target_root_path, selected_candidates)

        _append_log(log_path, f"{_workflow_public_id()} start: runs={len(selected_candidates)} total_size={required}")

        for candidate in selected_candidates:
            rec: dict[str, Any] = {
                "instrument": candidate.instrument,
                "run_id": candidate.run_id,
                "owner_user": candidate.owner_user,
                "run_date": candidate.run_date.isoformat(),
                "retention_reference_date": candidate.retention_reference_date.isoformat(),
                "retention_reference_source": candidate.retention_reference_source,
                "source": str(candidate.source_path),
                "target": str(candidate.target_run_path),
                "size_bytes": candidate.size_bytes,
                "copy_status": "pending",
                "verify_status": "pending",
                "cleanup_status": "pending_external_cleanup",
                "status": "planned",
                "errors": [],
                "log_path": str(log_path),
            }

            if dry_run:
                rec["copy_status"] = "skipped_dry_run"
                rec["verify_status"] = "skipped_dry_run"
                rec["status"] = "dry_run_only"
                records.append(rec)
                print(_warn(f"[dry-run] Would archive {candidate.source_path} -> {candidate.target_run_path}"))
                _write_manifest(manifest_path, metadata, records)
                continue

            _append_log(log_path, f"run_start {candidate.run_id}")
            try:
                _rsync_copy(candidate)
                rec["copy_status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                rec["copy_status"] = "failed"
                rec["verify_status"] = "skipped_due_to_copy_failure"
                rec["status"] = "failed"
                rec["errors"].append(f"copy: {exc}")
                copy_failures += 1
                _append_log(log_path, f"run_copy_failed {candidate.run_id}: {exc}")
                records.append(rec)
                _write_manifest(manifest_path, metadata, records)
                continue

            try:
                _rsync_verify(candidate)
                rec["verify_status"] = "ok"
                rec["status"] = "copied_verified"
                _append_log(log_path, f"run_verified {candidate.run_id}")
            except Exception as exc:  # noqa: BLE001
                rec["verify_status"] = "failed"
                rec["status"] = "failed"
                rec["errors"].append(f"verify: {exc}")
                verify_failures += 1
                _append_log(log_path, f"run_verify_failed {candidate.run_id}: {exc}")

            records.append(rec)
            _write_manifest(manifest_path, metadata, records)

        _append_log(
            log_path,
            f"{_workflow_public_id()} done: processed={len(records)} copy_failures={copy_failures} verify_failures={verify_failures}",
        )

        _print_section("Done")
        print(_ok(f"Manifest: {manifest_path}"))
        print(_ok(f"Log: {log_path}"))
        print(_ok(f"Processed runs: {len(records)}"))
        print(_ok(f"Copy-failed runs: {copy_failures}" if copy_failures == 0 else f"Copy-failed runs: {copy_failures}"))
        if verify_failures:
            print(_err(f"Verify-failed runs: {verify_failures}"))
        else:
            print(_ok("Verify-failed runs: 0"))

        if copy_failures or verify_failures:
            raise SystemExit(1)
    finally:
        _release_lock(lock_fd, lock_path)


if __name__ == "__main__":
    main()
