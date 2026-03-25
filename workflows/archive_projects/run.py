#!/usr/bin/env python3
from __future__ import annotations
import argparse
import configparser
import csv
import fnmatch
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
DEFAULT_SOURCE_ROOT = "/data/projects"
DEFAULT_TARGET_ROOT = "/mnt/nextgen2/archive/projects"
DEFAULT_RETENTION_DAYS = 90
DEFAULT_MANIFEST_DIR = "/data/shared/bpm_manifests"
DEFAULT_KEEP_RULES_PATH = "/data/shared/bpm_manifests/keep_rules.yaml"
DEFAULT_EXCLUDE_PATTERNS = [
    "work",
    ".pixi",
    ".renv",
    ".nextflow",
    "results",
    "*.fastq.gz",
]
DEFAULT_INSTRUMENTS = [
    "miseq1_M00818",
    "miseq2_M04404",
    "miseq3_M00403",
    "nextseq500_NB501289",
    "novaseq_A01742",
]
RUN_PREFIX_RE = re.compile(r"^(?P<prefix>\d{6})_")
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
def _cmd(text: str) -> str:
    return _style(text, "36")
def _dim(text: str) -> str:
    return _style(text, "2")
@dataclass
class RunCandidate:
    run_id: str
    owner_user: str
    project_id: str | None
    run_date: date
    retention_reference_date: date
    retention_reference_source: str
    source_path: Path
    target_instrument_path: Path
    target_run_path: Path
    total_size_bytes: int
    archive_size_bytes: int | None
    kept_by_rule: bool = False
    cleanup_only: bool = False
    cleanup_only_reason: str | None = None
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
            return "quit"
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

def _render_progress(prefix: str, current: int, total: int, detail: str = "") -> None:
    if total <= 0 or not sys.stdout.isatty():
        return
    width = 24
    filled = min(width, int(width * current / total))
    bar = "#" * filled + "-" * (width - filled)
    suffix = f" {detail}" if detail else ""
    line = f"\r{prefix} [{bar}] {current}/{total}{suffix}"
    print(line[: max(0, shutil.get_terminal_size((120, 20)).columns - 1)], end="", flush=True)


def _finish_progress() -> None:
    if sys.stdout.isatty():
        print()
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
def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}
def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}
def _nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
def _project_name_from_ini(path: Path) -> str | None:
    ini_path = path / 'project.ini'
    if not ini_path.is_file():
        return None
    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding='utf-8')
    except Exception:  # noqa: BLE001
        return None
    if not parser.has_section('Project'):
        return None
    project_name = parser.get('Project', 'project_name', fallback='').strip()
    return project_name or None
def _sample_project_from_samplesheet(path: Path) -> str | None:
    for filename in ('samplesheet.csv', 'samplesheet_bclconvert.csv'):
        samplesheet = path / filename
        if not samplesheet.is_file():
            continue
        current_section: str | None = None
        try:
            with samplesheet.open('r', encoding='utf-8', newline='') as fh:
                for raw_line in fh:
                    row = next(csv.reader([raw_line]))
                    first = row[0].strip() if row else ''
                    if not first:
                        continue
                    if first.startswith('[') and first.endswith(']'):
                        current_section = first[1:-1].strip()
                        continue
                    if current_section not in {'BCLConvert_Data', 'Data'}:
                        continue
                    try:
                        project_idx = row.index('Sample_Project')
                    except ValueError:
                        return None
                    for data_line in fh:
                        data_row = next(csv.reader([data_line]))
                        first = data_row[0].strip() if data_row else ''
                        if not first:
                            continue
                        if first.startswith('[') and first.endswith(']'):
                            return None
                        if project_idx >= len(data_row):
                            continue
                        project_name = data_row[project_idx].strip()
                        if project_name:
                            return project_name
                    return None
        except Exception:  # noqa: BLE001
            return None
    return None
def _project_id_from_folder(path: Path) -> str | None:
    bpm_meta = _load_yaml_file(path / 'bpm.meta.yaml')
    project_name = _nested_get(bpm_meta, 'export', 'demux', 'project_name')
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()
    export_job_spec = _load_json_file(path / 'export_job_spec.json')
    project_name = export_job_spec.get('project_name')
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()
    project_name = _sample_project_from_samplesheet(path)
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()
    project_name = _project_name_from_ini(path)
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()
    project_meta = _load_yaml_file(path / 'project.yaml')
    project_name = project_meta.get('name')
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()
    return None
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
def _dir_size_excluding(path: Path, exclude_patterns: list[str]) -> int:
    total = 0
    for root, _, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            if _match_exclude_pattern(file_path, path, exclude_patterns) is not None:
                continue
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total
def _has_excluded_files(path: Path, exclude_patterns: list[str]) -> bool:
    for root, _, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            if _match_exclude_pattern(file_path, path, exclude_patterns) is not None:
                return True
    return False
def _has_any_files(path: Path) -> bool:
    for root, _, files in os.walk(path):
        if files:
            return True
    return False
def _match_exclude_pattern(file_path: Path, run_dir: Path, exclude_patterns: list[str]) -> str | None:
    name = file_path.name
    rel_path = file_path.relative_to(run_dir)
    rel = str(rel_path)
    parts = rel_path.parts
    for pat in exclude_patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return pat
        if pat in parts:
            return pat
    return None
def _is_preserved_file(path: Path, source_dir: Path, preserve_patterns: list[str]) -> bool:
    rel_path = path.relative_to(source_dir)
    rel = str(rel_path)
    name = path.name
    rel_parts = rel_path.parts
    for pat in preserve_patterns:
        cleaned = pat.strip().strip('/')
        if not cleaned:
            continue
        if fnmatch.fnmatch(name, cleaned) or fnmatch.fnmatch(rel, cleaned):
            return True
        if all(ch not in cleaned for ch in '*?[]'):
            if cleaned in rel_parts:
                return True
            if rel.startswith(cleaned + '/'):
                return True
        if fnmatch.fnmatch(rel, cleaned + '/*'):
            return True
    return False
def _is_safe_flat_run_path(source_dir: Path, source_root: Path) -> tuple[bool, str]:
    if not source_dir.is_absolute():
        return False, 'source path is not absolute'
    resolved = source_dir.resolve(strict=False)
    root_resolved = source_root.resolve(strict=False)
    try:
        rel_parts = resolved.relative_to(root_resolved).parts
    except ValueError:
        return False, 'source path is outside source root'
    if len(rel_parts) != 1:
        return False, 'source path is not a direct child run directory of source root'
    if source_dir.is_symlink() or resolved.is_symlink():
        return False, 'refusing to remove symlinked run directory'
    if resolved == root_resolved:
        return False, 'refusing to remove source root'
    return True, ''
def _cleanup_run_directory(source_dir: Path, source_root: Path, dry_run: bool) -> tuple[int, int, str]:
    ok, reason = _is_safe_flat_run_path(source_dir, source_root)
    if not ok:
        raise RuntimeError(reason)
    if not source_dir.exists():
        return 0, 0, 'skipped_missing'
    if dry_run:
        print(_warn(f'[dry-run] Would remove run directory: {source_dir}'))
        return 0, 0, 'dry_run_only'
    file_count = sum(1 for p in source_dir.rglob('*') if p.is_file() and not p.is_symlink())
    dir_count = sum(1 for p in source_dir.rglob('*') if p.is_dir())
    shutil.rmtree(source_dir)
    return file_count, dir_count + 1, 'done'
def _compute_cutoff(retention_days: int) -> date:
    return date.today() - timedelta(days=retention_days)
def _subtree_sizes(path: Path, run_dir: Path, exclude_patterns: list[str]) -> tuple[int, int]:
    total = 0
    archive = 0
    if path.is_file():
        try:
            total = path.stat().st_size
        except OSError:
            return 0, 0
        if _match_exclude_pattern(path, run_dir, exclude_patterns) is None:
            archive = total
        return total, archive
    for root, _, files in os.walk(path):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            total += size
            if _match_exclude_pattern(file_path, run_dir, exclude_patterns) is None:
                archive += size
    return total, archive


def _top_level_breakdown(run_dir: Path, exclude_patterns: list[str]) -> list[tuple[str, int, int]]:
    rows: list[tuple[str, int, int]] = []
    try:
        children = sorted(run_dir.iterdir(), key=lambda p: p.name.lower())
    except Exception:  # noqa: BLE001
        return rows
    for child in children:
        total, archive = _subtree_sizes(child, run_dir, exclude_patterns)
        rows.append((child.name + ('/' if child.is_dir() else ''), total, archive))
    rows.sort(key=lambda item: (item[2], item[1], item[0]), reverse=True)
    return rows


def _investigate_run(source_root: Path, run_id: str, exclude_patterns: list[str], top_n: int) -> None:
    run_dir = source_root / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise SystemExit(f"Investigate run not found or not a directory: {run_dir}")
    total_bytes = 0
    excluded_bytes = 0
    included_bytes = 0
    included_files: list[tuple[int, str]] = []
    excluded_files: list[tuple[int, str, str]] = []
    by_pattern: dict[str, int] = {}
    by_top_included: dict[str, int] = {}
    by_top_excluded: dict[str, int] = {}
    for root, _, files in os.walk(run_dir):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            rel = str(file_path.relative_to(run_dir))
            top = rel.split("/", 1)[0] if "/" in rel else "."
            total_bytes += size
            pat = _match_exclude_pattern(file_path, run_dir, exclude_patterns)
            if pat is not None:
                excluded_bytes += size
                excluded_files.append((size, rel, pat))
                by_pattern[pat] = by_pattern.get(pat, 0) + size
                by_top_excluded[top] = by_top_excluded.get(top, 0) + size
            else:
                included_bytes += size
                included_files.append((size, rel))
                by_top_included[top] = by_top_included.get(top, 0) + size
    def _top_items(items: list[tuple[int, str]], n: int) -> list[tuple[int, str]]:
        return sorted(items, key=lambda x: x[0], reverse=True)[:n]
    _print_section("Investigate Run")
    print(f"Run: {run_id}")
    print(f"Path: {run_dir}")
    print(f"Exclude patterns: {', '.join(exclude_patterns) if exclude_patterns else '(none)'}")
    print("\nSummary:")
    print(_ok(f"- Total size: {_format_bytes(total_bytes)}"))
    print(_warn(f"- Excluded by patterns: {_format_bytes(excluded_bytes)}"))
    print(_ok(f"- Included (archive size): {_format_bytes(included_bytes)}"))
    if by_pattern:
        print("\nExcluded size by pattern:")
        for pat, size in sorted(by_pattern.items(), key=lambda kv: kv[1], reverse=True):
            print(f"  {pat:<20} {_format_bytes(size):>12}")
    if by_top_included:
        print("\nTop-level included paths:")
        for name, size in sorted(by_top_included.items(), key=lambda kv: kv[1], reverse=True)[:top_n]:
            print(f"  {name:<36} {_format_bytes(size):>12}")
    if by_top_excluded:
        print("\nTop-level excluded paths:")
        for name, size in sorted(by_top_excluded.items(), key=lambda kv: kv[1], reverse=True)[:top_n]:
            print(f"  {name:<36} {_format_bytes(size):>12}")
    top_inc = _top_items(included_files, top_n)
    if top_inc:
        print("\nTop included files:")
        for size, rel in top_inc:
            print(f"  {_format_bytes(size):>12}  {rel}")
    top_exc = sorted(excluded_files, key=lambda x: x[0], reverse=True)[:top_n]
    if top_exc:
        print("\nTop excluded files:")
        for size, rel, pat in top_exc:
            print(f"  {_format_bytes(size):>12}  {rel}  {_dim(f'({pat})')}")
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
    exclude_patterns: list[str],
    progress_prefix: str | None = None,
) -> tuple[list[RunCandidate], list[str]]:
    # /data/projects is a flat run layout (no instrument-level folders).
    # Keep "instruments" argument for interface compatibility; it is ignored here.
    _ = instruments
    issues: list[str] = []
    cutoff = _compute_cutoff(retention_days)
    candidates: list[RunCandidate] = []
    entries = sorted(source_root.iterdir())
    total_entries = len(entries)
    for idx, entry in enumerate(entries, start=1):
        try:
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
                total_size_bytes = _du_size_bytes(entry)
                project_id = _project_id_from_folder(entry)
                kept_by_rule = entry.name in keep_run_ids
                archive_size_bytes = None
                cleanup_only = False
                cleanup_only_reason = None
                if not kept_by_rule:
                    archive_size_bytes = _dir_size_excluding(entry, exclude_patterns)
                    if archive_size_bytes == 0:
                        if _has_excluded_files(entry, exclude_patterns):
                            if (target_root / entry.name).is_dir():
                                cleanup_only = True
                                cleanup_only_reason = 'already-cleaned/excluded-only'
                                issues.append(f"Including cleanup-only run with existing archive target: {entry.name}")
                            else:
                                issues.append(f"Skipping already-cleaned/excluded-only run without archive target: {entry.name}")
                                continue
                        elif not _has_any_files(entry):
                            if (target_root / entry.name).is_dir():
                                cleanup_only = True
                                cleanup_only_reason = 'already-cleaned/empty'
                                issues.append(f"Including cleanup-only run with existing archive target: {entry.name}")
                            else:
                                issues.append(f"Skipping already-cleaned/empty run without archive target: {entry.name}")
                                continue
            except Exception as exc:  # noqa: BLE001
                issues.append(f"Failed to calculate size for {entry}: {exc}")
                continue
            candidates.append(
                RunCandidate(
                    run_id=entry.name,
                    owner_user=_owner_user(entry),
                    project_id=project_id,
                    run_date=run_date,
                    retention_reference_date=ref_date,
                    retention_reference_source=ref_source,
                    source_path=entry,
                    target_instrument_path=target_root,
                    target_run_path=target_root / entry.name,
                    total_size_bytes=total_size_bytes,
                    archive_size_bytes=archive_size_bytes,
                    kept_by_rule=kept_by_rule,
                    cleanup_only=cleanup_only,
                    cleanup_only_reason=cleanup_only_reason,
                )
            )
        finally:
            if progress_prefix:
                _render_progress(progress_prefix, idx, total_entries, entry.name)
    candidates.sort(key=lambda c: (c.run_date, c.run_id))
    return candidates, issues
def _print_section(title: str) -> None:
    print("\n" + _title("=" * 80))
    print(_title(title))
    print(_title("=" * 80))
def _run_archive_tui(candidates: list[RunCandidate], rules_path: Path) -> str:
    import curses
    if not candidates:
        return "quit"
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
    def _curses_main(stdscr) -> tuple[str, int]:
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
        set_by_values = [set_by_map.get(c.run_id, "-") for c in candidates]
        details_visible = False
        details_cache: dict[str, list[tuple[str, int, int]]] = {}
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
            panel_min_width = 44
            panel_width = min(56, max(panel_min_width, w // 3)) if details_visible and w >= 120 else 0
            list_width = max(40, w - panel_width - (1 if panel_width else 0))
            stdscr.addnstr(0, 0, f"archive_projects | archive candidates | runs={len(candidates)}".ljust(max(0, w - 1)), w - 1, color_header)
            stdscr.addnstr(1, 0, "Only runs older than retention are shown. k: keep/unkeep  u: keep-until  d: details  s: save+continue  q: quit".ljust(max(0, w - 1)), w - 1, color_help)
            list_top = 4
            list_h = max(1, h - 6)
            owner_col = _column_width(owner_values, "Owner", min_width=5, max_width=12)
            set_by_col = _column_width(set_by_values, "Set By", min_width=6, max_width=12)
            fixed_width = 4 + 1 + 7 + 1 + 1 + owner_col + 1 + 10 + 1 + set_by_col + 1 + 10 + 1 + 10
            run_col = max(18, min(max(len(r) for r in run_ids), max(18, list_width - fixed_width - 1)))
            row_fmt = f"{{keep:<4}} {{archive:<7}} {{run:<{run_col}}} {{owner:<{owner_col}}} {{ku:<10}} {{set_by:<{set_by_col}}} {{total:>10}} {{arch_size:>10}}"
            header = row_fmt.format(keep="Keep", archive="Archive", run="Run ID", owner="Owner", ku="Keep Until", set_by="Set By", total="Total", arch_size="ArchSize")
            stdscr.addnstr(3, 0, header.ljust(max(0, list_width - 1)), max(0, list_width - 1), color_help | curses.A_BOLD)
            if idx < top:
                top = idx
            elif idx >= top + list_h:
                top = idx - list_h + 1
            for row in range(list_h):
                pos = top + row
                y = list_top + row
                if pos >= len(candidates):
                    stdscr.addnstr(y, 0, " " * max(0, list_width - 1), max(0, list_width - 1), color_row)
                    continue
                item = candidates[pos]
                archive_state = 'no' if marked.get(item.run_id, False) else ('cleanup' if item.cleanup_only else 'yes')
                row_values = dict(
                    keep='yes' if marked.get(item.run_id, False) else 'no',
                    archive=archive_state,
                    run=_clip(item.run_id, run_col),
                    owner=_clip(item.owner_user, owner_col),
                    ku=(keep_until.get(item.run_id) or '-'),
                    set_by=_clip(set_by_map.get(item.run_id, '-'), set_by_col),
                    total=_format_bytes(item.total_size_bytes),
                    arch_size='-' if marked.get(item.run_id, False) or item.archive_size_bytes is None or item.cleanup_only else _format_bytes(item.archive_size_bytes),
                )
                line = row_fmt.format(**row_values)
                attr = color_selected if pos == idx else (color_marked if marked.get(item.run_id, False) else color_row)
                stdscr.addnstr(y, 0, line.ljust(max(0, list_width - 1)), max(0, list_width - 1), attr)
            active_candidates = [c for c in candidates if not marked.get(c.run_id, False)]
            archive_count = sum(1 for c in active_candidates if not c.cleanup_only)
            cleanup_only_count = sum(1 for c in active_candidates if c.cleanup_only)
            kept_count = len(candidates) - len(active_candidates)
            total_archive = sum((c.archive_size_bytes or 0) for c in active_candidates if not c.cleanup_only)
            stdscr.addnstr(h - 2, 0, f"Will archive: {archive_count}  Cleanup-only: {cleanup_only_count}  Kept: {kept_count}  Archive size: {_format_bytes(total_archive)}".ljust(max(0, w - 1)), w - 1, color_summary)
            stdscr.addnstr(h - 1, 0, status.ljust(max(0, w - 1)), w - 1, color_status if status else color_row)
            if panel_width and candidates:
                panel_x = list_width
                stdscr.vline(3, panel_x, curses.ACS_VLINE, max(1, h - 3))
                selected = candidates[idx]
                rows = details_cache.get(selected.run_id, [])
                stdscr.addnstr(3, panel_x + 1, _clip(f"Details: {selected.run_id}", panel_width - 2).ljust(max(0, panel_width - 2)), max(0, panel_width - 2), color_help | curses.A_BOLD)
                stdscr.addnstr(4, panel_x + 1, _clip("Path                              Archive      Total", panel_width - 2).ljust(max(0, panel_width - 2)), max(0, panel_width - 2), color_help)
                visible_rows = max(0, h - 8)
                if rows:
                    name_width = max(8, panel_width - 2 - 12 - 11)
                    for i, (name, total_size, archive_size) in enumerate(rows[:visible_rows]):
                        flag = " excl" if archive_size == 0 and total_size > 0 else ""
                        line = f"{_clip(name, name_width):<{name_width}} {_format_bytes(archive_size):>10} {_format_bytes(total_size):>10}{flag}"
                        stdscr.addnstr(5 + i, panel_x + 1, _clip(line, panel_width - 2).ljust(max(0, panel_width - 2)), max(0, panel_width - 2), color_row)
                else:
                    stdscr.addnstr(5, panel_x + 1, _clip("Press d to load top-level subfolder sizes.", panel_width - 2).ljust(max(0, panel_width - 2)), max(0, panel_width - 2), color_help)
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
            elif key == ord('d'):
                if stdscr.getmaxyx()[1] < 120:
                    _render('Details panel needs a wider terminal (>= 120 columns).')
                    continue
                item = candidates[idx]
                details_visible = not details_visible
                if details_visible and item.run_id not in details_cache:
                    _render('Calculating top-level subfolder sizes...')
                    details_cache[item.run_id] = _top_level_breakdown(item.source_path, exclude_patterns)
                    _render('Loaded top-level subfolder sizes.')
                else:
                    _render()
            elif key == ord('s'):
                saved_changes = _save()
                _render(f'Saved keep changes: {saved_changes}. Continuing...')
                curses.napms(700)
                return 'continue', saved_changes
            elif key == ord('q'):
                if changed:
                    _render('Unsaved changes. Press q again to discard and quit.')
                    if stdscr.getch() == ord('q'):
                        return 'quit', 0
                    _render()
                    continue
                return 'quit', 0
    action, _ = curses.wrapper(_curses_main)
    return action
def _print_plan(
    candidates: list[RunCandidate],
    retention_days: int,
    skip_runs: set[str],
    keep_run_ids: set[str],
    exclude_patterns: list[str],
) -> None:
    cutoff = _compute_cutoff(retention_days)
    _print_section("Archive Plan")
    print(f"Retention days: {retention_days}")
    print(f"Archive runs older than: {cutoff.isoformat()} (strictly before this date)")
    print("Retention reference: export.last_exported_at -> run-name YYMMDD prefix")
    print(f"Runs skipped by user: {', '.join(sorted(skip_runs)) if skip_runs else '(none)'}")
    print(f"Runs protected by keep_rules: {len(keep_run_ids)}")
    print(f"Exclude patterns: {', '.join(exclude_patterns) if exclude_patterns else '(none)'}")
    if not candidates:
        print("\nNo run directories match the archive criteria.")
        return
    run_col = max(38, min(54, max(len(c.run_id) for c in candidates) + 2))
    owner_col = max(8, min(14, max(len(c.owner_user) for c in candidates) + 2))
    status_col = 20
    total_col = 14
    arch_col = 24
    row_fmt = (
        f"{{no:>4}}  {{run:<{run_col}}}{{owner:<{owner_col}}}"
        f"{{status:<{status_col}}}{{total:>{total_col}}}  {{arch:>{arch_col}}}"
    )
    print("\nSelected runs:")
    header_values = dict(
        no="No.",
        run="Run ID",
        owner="Owner",
        status="Status",
        total="Total Size",
        arch="Archive Size (after excludes)",
    )
    header = row_fmt.format(**header_values)
    print(_dim(header))
    print(_dim("-" * len(header)))
    for idx, item in enumerate(candidates, start=1):
        row_values = dict(
            no=f"{idx}.",
            run=item.run_id,
            owner=item.owner_user,
            status=("kept (not archived)" if item.kept_by_rule else ("cleanup-only" if item.cleanup_only else "selected")),
            total=_format_bytes(item.total_size_bytes),
            arch="-" if item.kept_by_rule or item.archive_size_bytes is None or item.cleanup_only else _format_bytes(item.archive_size_bytes),
        )
        print(row_fmt.format(**row_values))
    selected = [c for c in candidates if not c.kept_by_rule]
    kept = [c for c in candidates if c.kept_by_rule]
    archive_selected = [c for c in selected if not c.cleanup_only]
    cleanup_only_selected = [c for c in selected if c.cleanup_only]
    total_all = sum(c.total_size_bytes for c in archive_selected)
    total_archive = sum(c.archive_size_bytes or 0 for c in archive_selected)
    total_excluded = max(0, total_all - total_archive)
    print("\nSummary:")
    print(_ok(f"- Selected run count: {len(selected)}"))
    print(_ok(f"- Archive run count: {len(archive_selected)}"))
    print(_ok(f"- Cleanup-only run count: {len(cleanup_only_selected)}"))
    print(_warn(f"- Kept run count: {len(kept)}"))
    print(_ok(f"- Total size (all files, archive runs): {_format_bytes(total_all)}"))
    print(_ok(f"- Total size (to archive, after excludes): {_format_bytes(total_archive)}"))
    print(_warn(f"- Total size excluded by patterns: {_format_bytes(total_excluded)}"))
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
    _print_section("archive_projects Interactive Setup")
    print(_dim("Press Enter to keep defaults."))
    source_root = _input_with_default("Source root", source_root)
    target_root = _input_with_default("Target root", target_root)
    retention_raw = _input_with_default("Retention days", str(retention_days))
    try:
        retention_days = int(retention_raw)
    except ValueError:
        raise SystemExit(f"Invalid retention days: {retention_raw}")
    # archive_projects uses a flat source layout; instrument_folders is intentionally ignored.
    skip_default = ",".join(sorted(skip_runs))
    skip_raw = _input_with_default("Skip run IDs (comma-separated; optional)", skip_default)
    skip_runs = set(_split_csv(skip_raw))
    return source_root, target_root, retention_days, instruments, skip_runs
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
        with tempfile.NamedTemporaryFile(prefix=".archive_projects_write_test_", dir=path, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Cannot write to target directory {path}: {exc}") from exc
def _preflight_target_paths(target_root: Path, candidates: list[RunCandidate]) -> None:
    _assert_writable_dir(target_root)
    seen_instruments: set[Path] = set()
    seen_runs: set[Path] = set()
    for candidate in candidates:
        instrument_dir = candidate.target_instrument_path
        if instrument_dir not in seen_instruments:
            if not instrument_dir.exists():
                try:
                    instrument_dir.mkdir(parents=True, exist_ok=True)
                except Exception as exc:  # noqa: BLE001
                    raise SystemExit(f"Failed to create target instrument directory {instrument_dir}: {exc}") from exc
            _assert_writable_dir(instrument_dir)
            seen_instruments.add(instrument_dir)
        target_run_dir = candidate.target_run_path
        if target_run_dir in seen_runs:
            continue
        if target_run_dir.exists():
            if not target_run_dir.is_dir():
                raise SystemExit(f"Target run path exists and is not a directory: {target_run_dir}")
            _assert_writable_dir(target_run_dir)
        seen_runs.add(target_run_dir)
def _run_cmd(cmd: list[str], *, quiet_success: bool = False) -> subprocess.CompletedProcess[str]:
    print(_cmd("+ " + " ".join(cmd)))
    result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, end='' if result.stderr.endswith('\n') else '\n', file=sys.stderr)
        elif result.stdout:
            print(result.stdout, end='' if result.stdout.endswith('\n') else '\n')
        raise RuntimeError(_summarize_command_failure(cmd, result))
    if not quiet_success:
        summary = _rsync_progress_summary(result.stdout)
        if summary:
            print(_dim(summary))
    return result
def _rsync_copy(candidate: RunCandidate, exclude_patterns: list[str]) -> None:
    candidate.target_instrument_path.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rsync",
        "-a",
        "--human-readable",
        "--info=progress2",
        "--no-inc-recursive",
        "--partial",
        "--omit-dir-times",
        "--no-perms",
        "--no-group",
    ]
    for pat in exclude_patterns:
        cmd.extend(["--exclude", pat])
    cmd.extend([str(candidate.source_path), str(candidate.target_instrument_path)])
    _run_cmd(cmd, quiet_success=True)
def _rsync_verify(candidate: RunCandidate, exclude_patterns: list[str]) -> None:
    cmd = [
        "rsync",
        "-avhn",
        "--omit-dir-times",
        "--no-perms",
        "--no-group",
    ]
    for pat in exclude_patterns:
        cmd.extend(["--exclude", pat])
    cmd.extend([f"{candidate.source_path}/", f"{candidate.target_run_path}/"])
    verify = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
    )
    if verify.returncode != 0:
        raise RuntimeError(_summarize_command_failure(cmd, verify))
    lines = [line.strip() for line in verify.stdout.splitlines() if line.strip()]
    payload_lines = [line for line in lines if not line.startswith(("sending ", "sent ", "total size is "))]
    if payload_lines:
        preview = "; ".join(payload_lines[:5])
        if len(payload_lines) > 5:
            preview += f"; ... (+{len(payload_lines) - 5} more)"
        raise RuntimeError(
            "Verification mismatch after copy for "
            f"{candidate.run_id}. First rsync diff lines: {preview}"
        )
def _acquire_lock(lock_path: Path) -> int:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags)
    except FileExistsError:
        try:
            raw = lock_path.read_text(encoding='utf-8').strip()
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
    os.write(fd, str(os.getpid()).encode('utf-8'))
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
def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('+ rsync '):
            continue
        return stripped
    return ''
def _summarize_command_failure(cmd: list[str], result: subprocess.CompletedProcess[str]) -> str:
    stderr_first = _first_meaningful_line(result.stderr or '')
    stdout_first = _first_meaningful_line(result.stdout or '')
    detail = stderr_first or stdout_first or f'command exited with status {result.returncode}'
    return f"{' '.join(cmd)} -> {detail} (exit {result.returncode})"
def _rsync_progress_summary(stdout: str) -> str | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if '(xfr#' in line:
            return line
    return None
def _classify_failure(rec: dict[str, Any]) -> tuple[str, str]:
    messages: list[str] = []
    messages.extend(str(e) for e in rec.get('errors') or [])
    cleanup_error = str(rec.get('cleanup_error') or '').strip()
    if cleanup_error:
        messages.append(cleanup_error)
    blob = '\n'.join(messages).lower()
    source_path = str(rec.get('source') or '').lower()
    target_path = str(rec.get('target') or '').lower()
    if 'permission denied' in blob and str(rec.get('copy_status')) == 'failed':
        if '[sender]' in blob or 'send_files failed to open' in blob or (source_path and source_path in blob):
            return (
                'source read permission denied',
                'Fix ownership/permissions on the source run files so archive_projects can read them.',
            )
        if '[receiver]' in blob or '[generator]' in blob or (target_path and target_path in blob):
            return (
                'archive target permission denied',
                'Fix ownership/permissions under the target archive run directory and rerun archive_projects.',
            )
        return (
            'copy permission denied',
            'Check both source-read and target-write permissions for this run before rerunning.',
        )
    if 'operation not permitted' in blob and str(rec.get('copy_status')) == 'failed':
        return (
            'archive target metadata/permission restriction',
            'Check mount/ACL behavior on the target archive filesystem; directory writes are restricted there.',
        )
    if 'permission denied' in blob and str(rec.get('cleanup_status')) == 'failed':
        return (
            'source cleanup permission denied',
            'Fix ownership/permissions in the source run directory so the workflow can remove the archived run folder.',
        )
    if str(rec.get('verify_status')) == 'failed':
        return (
            'archive verify failed',
            'The preview shows the first rsync delete/add paths. If they are archived-only files, the source run was likely already cleaned and should be skipped on rerun.',
        )
    if 'rsync' in blob and str(rec.get('copy_status')) == 'failed':
        return (
            'rsync copy failed',
            'Inspect the per-run error and log output, then fix the target path or file-level permission issue before rerunning.',
        )
    if str(rec.get('cleanup_status')) == 'failed':
        return (
            'cleanup failed',
            'Inspect the cleanup_error field in the manifest and fix the remaining source-side permission or path issue.',
        )
    return ('failed', 'Inspect the manifest/log for details and rerun after resolving the issue.')
def _print_failure_details(records: list[dict[str, Any]]) -> None:
    failed = [rec for rec in records if rec.get('status') == 'failed']
    if not failed:
        return
    print(_err('Batch completed with failures.'))
    categories: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rec in failed:
        key = _classify_failure(rec)
        categories.setdefault(key, []).append(rec)
    print('\nFailure details:')
    for (label, hint), recs in categories.items():
        run_ids = ', '.join(str(rec.get('run_id') or '-') for rec in recs)
        print(_err(f'- {label}: {len(recs)}'))
        print(f'  Runs: {run_ids}')
        sample = recs[0]
        sample_msgs = [str(e) for e in sample.get('errors') or []]
        cleanup_error = str(sample.get('cleanup_error') or '').strip()
        if cleanup_error:
            sample_msgs.append(cleanup_error)
        if sample_msgs:
            print(f'  Example: {sample_msgs[0]}')
        print(f'  Suggested fix: {hint}')
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
        with tempfile.NamedTemporaryFile(prefix=".archive_projects_manifest_write_test_", dir=manifest_path.parent, delete=True):
            pass
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(_manifest_setup_hint(manifest_path.parent) + f"\nDetail: {exc}") from exc
    try:
        with tempfile.NamedTemporaryFile(prefix=".archive_projects_log_write_test_", dir=log_path.parent, delete=True):
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
    parser = argparse.ArgumentParser(description="Archive old project run folders with rsync.")
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--target-root", default=DEFAULT_TARGET_ROOT)
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--instrument-folders", default=",".join(DEFAULT_INSTRUMENTS))
    parser.add_argument("--skip-runs", default="")
    parser.add_argument("--non-interactive", nargs="?", const="true", default="false")
    parser.add_argument("--interactive", nargs="?", const="true", default="true")
    parser.add_argument("--yes", nargs="?", const="true", default="false")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")
    parser.add_argument("--cleanup", nargs="?", const="true", default="true")
    parser.add_argument("--min-free-gb", type=int, default=500)
    parser.add_argument("--manifest-path", default="")
    parser.add_argument("--manifest-dir", default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--exclude-patterns", default=",".join(DEFAULT_EXCLUDE_PATTERNS))
    parser.add_argument("--keep-rules-path", default=DEFAULT_KEEP_RULES_PATH)
    parser.add_argument("--tui", nargs="?", const="true", default="true")
    parser.add_argument("--investigate", default="")
    parser.add_argument("--investigate-top", type=int, default=20)
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
        "exclude_patterns": args.exclude_patterns,
        "keep_rules_path": args.keep_rules_path,
        "tui": args.tui,
        "investigate": args.investigate,
        "investigate_top": args.investigate_top,
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
    cleanup_requested = _parse_bool(params.get("cleanup"), True)
    yes = _parse_bool(params.get("yes"), False)
    min_free_gb = _parse_int(params.get("min_free_gb"), 500)
    manifest_path_raw = str(params.get("manifest_path") or "").strip()
    manifest_dir = Path(str(params.get("manifest_dir") or DEFAULT_MANIFEST_DIR)).expanduser().resolve()
    exclude_patterns = _split_csv(params.get("exclude_patterns") or ",".join(DEFAULT_EXCLUDE_PATTERNS))
    keep_rules_path = Path(str(params.get("keep_rules_path") or DEFAULT_KEEP_RULES_PATH)).expanduser().resolve()
    tui = _parse_bool(params.get("tui"), True)
    investigate_run_id = str(params.get("investigate") or "").strip()
    investigate_top = _parse_int(params.get("investigate_top"), 20)
    for mandatory in DEFAULT_EXCLUDE_PATTERNS:
        if mandatory not in exclude_patterns:
            exclude_patterns.append(mandatory)
    if retention_days < 0:
        raise SystemExit("retention_days must be >= 0")
    if investigate_top <= 0:
        raise SystemExit("investigate_top must be > 0")
    if non_interactive:
        interactive = False
        yes = True
        print(_dim("[mode] non_interactive=true -> interactive disabled, global confirmation auto-approved"))
    if investigate_run_id:
        interactive = False
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
    if investigate_run_id:
        _investigate_run(source_root_path, investigate_run_id, exclude_patterns, investigate_top)
        return
    if not target_root_path.exists() or not target_root_path.is_dir():
        raise SystemExit(f"Target root not found or not a directory: {target_root_path}")
    keep_run_ids, keep_notes = _shared_load_active_keep_runs(keep_rules_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_manifest_path = manifest_dir / f"archive_projects_{timestamp}.json"
    manifest_path = Path(manifest_path_raw).expanduser().resolve() if manifest_path_raw else default_manifest_path
    log_path = manifest_path.parent / f"{manifest_path.stem}.log"
    _print_section("Path Confirmation")
    print(f"Source root: {source_root_path}")
    print(f"Target root: {target_root_path}")
    print("Source layout: flat project directories (no instrument folders)")
    print(f"Keep rules path: {keep_rules_path}")
    print(f"Protected runs from keep rules: {len(keep_run_ids)}")
    print(f"Manifest path: {manifest_path}")
    print(f"Log path: {log_path}")
    print(f"Rsync exclude patterns: {', '.join(exclude_patterns) if exclude_patterns else '(none)'}")
    # Fail fast before expensive discovery/copy if manifest/log location is not writable.
    _preflight_manifest_paths(manifest_path, log_path)
    print(_dim("Scanning project directories and calculating archive sizes..."))
    candidates, issues = _discover_candidates(
        source_root=source_root_path,
        target_root=target_root_path,
        instruments=instruments,
        retention_days=retention_days,
        skip_runs=skip_runs,
        keep_run_ids=keep_run_ids,
        exclude_patterns=exclude_patterns,
        progress_prefix="scan",
    )
    _finish_progress()
    if issues or keep_notes:
        _print_section("Discovery Notes")
        for issue in issues:
            print(_warn(f"- {issue}"))
        for note in keep_notes:
            print(_warn(f"- {note}"))
    if interactive and sys.stdin.isatty() and tui and candidates:
        tui_action = _run_archive_tui(candidates, keep_rules_path)
        if tui_action == "quit":
            print(_warn("\nCancelled from TUI."))
            return
        keep_run_ids, keep_notes = _shared_load_active_keep_runs(keep_rules_path)
        print(_dim("Rescanning project directories after keep-rule updates..."))
        candidates, issues = _discover_candidates(
            source_root=source_root_path,
            target_root=target_root_path,
            instruments=instruments,
            retention_days=retention_days,
            skip_runs=skip_runs,
            keep_run_ids=keep_run_ids,
            exclude_patterns=exclude_patterns,
            progress_prefix="scan",
        )
        _finish_progress()
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
        archive_candidates = [c for c in selected_candidates if not c.cleanup_only]
        cleanup_only_candidates = [c for c in selected_candidates if c.cleanup_only]
        kept_candidates = [c for c in candidates if c.kept_by_rule]
        print(_ok(f"Selected run count: {len(selected_candidates)}"))
        print(_ok(f"Archive run count: {len(archive_candidates)}"))
        print(_ok(f"Cleanup-only run count: {len(cleanup_only_candidates)}"))
        print(_warn(f"Kept run count: {len(kept_candidates)}"))
        print(_ok(f"Total size to archive: {_format_bytes(sum((c.archive_size_bytes or 0) for c in archive_candidates))}"))
        print(_ok(f"Source removal after verify: {'enabled' if cleanup_requested else 'disabled'}"))
    else:
        _print_plan(candidates, retention_days, skip_runs, keep_run_ids, exclude_patterns)
    selected_candidates = [c for c in candidates if not c.kept_by_rule]
    if not selected_candidates:
        print(_warn("\nNothing to archive. Exiting."))
        return
    if not yes:
        if not (interactive and sys.stdin.isatty()):
            raise SystemExit("Global confirmation required. Re-run with --yes or interactive mode.")
        if not _input_yes_no(f"Proceed with archive/copy/verify{'/cleanup' if cleanup_requested else ''} sequence for all selected runs?", default_yes=False):
            raise SystemExit("Cancelled by user.")
    lock_path = Path("/tmp/archive_projects.lock")
    try:
        lock_fd = _acquire_lock(lock_path)
    except FileExistsError:
        raise SystemExit(f"Another archive_projects process is running (lock exists: {lock_path})")
    metadata: dict[str, Any] = {
        "workflow_id": "archive_projects",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_root": str(source_root_path),
        "target_root": str(target_root_path),
        "retention_days": retention_days,
        "instrument_folders": instruments,
        "skip_runs": sorted(skip_runs),
        "keep_rules_path": str(keep_rules_path),
        "keep_protected_runs": sorted(keep_run_ids),
        "dry_run": dry_run,
        "cleanup_in_archive": cleanup_requested,
        "cleanup_mode": "full_run_directory" if cleanup_requested else "disabled",
        "archive_exclude_patterns": exclude_patterns,
        "log_path": str(log_path),
    }
    records: list[dict[str, Any]] = []
    copy_failures = 0
    verify_failures = 0
    try:
        required = sum(c.archive_size_bytes or 0 for c in selected_candidates)
        _ensure_target_free_space(target_root_path, required, min_free_gb)
        _preflight_target_paths(target_root_path, selected_candidates)
        _append_log(log_path, f"archive_projects start: runs={len(selected_candidates)} total_size={required}")
        for candidate in selected_candidates:
            rec: dict[str, Any] = {
                "run_id": candidate.run_id,
                "owner_user": candidate.owner_user,
                "run_date": candidate.run_date.isoformat(),
                "retention_reference_date": candidate.retention_reference_date.isoformat(),
                "retention_reference_source": candidate.retention_reference_source,
                "source": str(candidate.source_path),
                "target": str(candidate.target_run_path),
                "size_bytes": candidate.archive_size_bytes or 0,
                "archive_size_bytes": candidate.archive_size_bytes or 0,
                "total_size_bytes": candidate.total_size_bytes,
                "cleanup_only": candidate.cleanup_only,
                "cleanup_only_reason": candidate.cleanup_only_reason,
                "copy_status": "pending",
                "verify_status": "pending",
                "cleanup_status": "pending" if cleanup_requested else "skipped_disabled",
                "cleanup_mode": "full_run_directory" if cleanup_requested else "disabled",
                "status": "planned",
                "errors": [],
                "log_path": str(log_path),
            }
            if dry_run:
                if candidate.cleanup_only:
                    rec["copy_status"] = "skipped_already_archived"
                    rec["verify_status"] = "skipped_already_archived"
                    rec["status"] = "dry_run_only"
                    rec["cleanup_status"] = "dry_run_only" if cleanup_requested else "skipped_disabled"
                    print(_warn(f"[dry-run] Would remove already-archived source run directory: {candidate.source_path}"))
                else:
                    rec["copy_status"] = "skipped_dry_run"
                    rec["verify_status"] = "skipped_dry_run"
                    rec["status"] = "dry_run_only"
                    rec["cleanup_status"] = "dry_run_only" if cleanup_requested else "skipped_disabled"
                    print(_warn(f"[dry-run] Would archive {candidate.source_path} -> {candidate.target_run_path}"))
                records.append(rec)
                _write_manifest(manifest_path, metadata, records)
                continue
            _append_log(log_path, f"run_start {candidate.run_id}")
            if candidate.cleanup_only:
                rec["copy_status"] = "skipped_already_archived"
                rec["verify_status"] = "skipped_already_archived"
                rec["status"] = "already_archived"
                _append_log(log_path, f"run_already_archived {candidate.run_id}: reason={candidate.cleanup_only_reason or '-'}")
                print(_dim(f"[archive] already archived on target, cleanup-only: {candidate.run_id}"))
            else:
                print(_dim(f"[archive] copying {candidate.run_id} -> {candidate.target_run_path}"))
                try:
                    _rsync_copy(candidate, exclude_patterns)
                    rec["copy_status"] = "ok"
                    print(_ok(f"[archive] copied: {candidate.run_id}"))
                except Exception as exc:  # noqa: BLE001
                    rec["copy_status"] = "failed"
                    rec["verify_status"] = "skipped_due_to_copy_failure"
                    rec["cleanup_status"] = "skipped_due_to_copy_failure" if cleanup_requested else rec["cleanup_status"]
                    rec["status"] = "failed"
                    rec["errors"].append(f"copy: {exc}")
                    copy_failures += 1
                    _append_log(log_path, f"run_copy_failed {candidate.run_id}: {exc}")
                    print(_err(f"[archive] failed: {candidate.run_id}: {exc}"))
                    records.append(rec)
                    _write_manifest(manifest_path, metadata, records)
                    continue
                print(_dim(f"[verify] checking archived copy for {candidate.run_id}"))
                try:
                    _rsync_verify(candidate, exclude_patterns)
                    rec["verify_status"] = "ok"
                    rec["status"] = "copied_verified"
                    _append_log(log_path, f"run_verified {candidate.run_id}")
                    print(_ok(f"[verify] archived copy verified: {candidate.run_id}"))
                except Exception as exc:  # noqa: BLE001
                    rec["verify_status"] = "failed"
                    rec["cleanup_status"] = "skipped_due_to_verify_failure" if cleanup_requested else rec["cleanup_status"]
                    rec["status"] = "failed"
                    rec["errors"].append(f"verify: {exc}")
                    verify_failures += 1
                    _append_log(log_path, f"run_verify_failed {candidate.run_id}: {exc}")
                    print(_err(f"[verify] failed: {candidate.run_id}: {exc}"))
            cleanup_ready = (
                (candidate.cleanup_only and rec["copy_status"] == "skipped_already_archived" and rec["verify_status"] == "skipped_already_archived")
                or (rec["copy_status"] == "ok" and rec["verify_status"] == "ok")
            )
            if cleanup_ready and cleanup_requested:
                rec["cleanup_attempted_at"] = datetime.now().isoformat(timespec="seconds")
                remove_reason = "already archived target exists" if candidate.cleanup_only else "verified archive"
                print(_warn(f"[remove] removing source run directory after {remove_reason}: {candidate.run_id}"))
                try:
                    removed_files, removed_dirs, cleanup_status = _cleanup_run_directory(
                        candidate.source_path,
                        source_root_path,
                        dry_run,
                    )
                    rec["cleanup_removed_file_count"] = removed_files
                    rec["cleanup_removed_dir_count"] = removed_dirs
                    rec["cleanup_status"] = cleanup_status
                    rec["cleanup_error"] = ""
                    if cleanup_status in {"done", "done_no_matches"}:
                        rec["status"] = "already_archived_cleaned" if candidate.cleanup_only else "copied_verified_cleaned"
                    elif cleanup_status == "dry_run_only":
                        rec["status"] = "dry_run_only"
                    _append_log(
                        log_path,
                        f"run_cleaned {candidate.run_id}: status={cleanup_status} removed_files={removed_files} removed_dirs={removed_dirs}",
                    )
                    print(_ok(f"[remove] source run directory removed: {candidate.run_id}"))
                except Exception as exc:  # noqa: BLE001
                    rec["cleanup_status"] = "failed"
                    rec["cleanup_error"] = str(exc)
                    rec["status"] = "failed"
                    rec["errors"].append(f"cleanup: {exc}")
                    _append_log(log_path, f"run_cleanup_failed {candidate.run_id}: {exc}")
            elif cleanup_ready and not cleanup_requested:
                rec["cleanup_status"] = "skipped_disabled"
                rec["status"] = "already_archived_cleanup_skipped" if candidate.cleanup_only else rec["status"]
            records.append(rec)
            _write_manifest(manifest_path, metadata, records)
        cleanup_failures = sum(1 for rec in records if rec.get("cleanup_status") == "failed")
        cleanup_done = sum(1 for rec in records if rec.get("cleanup_status") in {"done", "done_no_matches"})
        _append_log(
            log_path,
            f"archive_projects done: processed={len(records)} copy_failures={copy_failures} verify_failures={verify_failures} cleanup_done={cleanup_done} cleanup_failures={cleanup_failures}",
        )
        if copy_failures or verify_failures or cleanup_failures:
            _print_section("Completed With Failures")
        else:
            _print_section("Done")
        print(_ok(f"Manifest: {manifest_path}"))
        print(_ok(f"Log: {log_path}"))
        print(_ok(f"Processed runs: {len(records)}"))
        if copy_failures:
            print(_err(f"Copy-failed runs: {copy_failures}"))
        else:
            print(_ok("Copy-failed runs: 0"))
        if verify_failures:
            print(_err(f"Verify-failed runs: {verify_failures}"))
        else:
            print(_ok("Verify-failed runs: 0"))
        if cleanup_requested:
            if cleanup_failures:
                print(_err(f"Cleanup-failed runs: {cleanup_failures}"))
            else:
                print(_ok(f"Cleaned runs: {cleanup_done}"))
        if copy_failures or verify_failures or cleanup_failures:
            _print_failure_details(records)
            raise SystemExit(1)
    finally:
        _release_lock(lock_fd, lock_path)
if __name__ == "__main__":
    main()
