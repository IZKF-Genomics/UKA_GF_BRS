from __future__ import annotations

import configparser
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import pwd
from typing import Any

import yaml


@dataclass(frozen=True)
class RunFolderInfo:
    run_id: str
    path: Path
    owner: str
    project_id: str | None


def path_owner(path: Path) -> str:
    try:
        uid = path.stat().st_uid
        return pwd.getpwuid(uid).pw_name
    except (KeyError, OSError):
        return "-"


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def project_name_from_ini(path: Path) -> str | None:
    ini_path = path / "project.ini"
    if not ini_path.is_file():
        return None

    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8")
    except Exception:  # noqa: BLE001
        return None

    if not parser.has_section("Project"):
        return None
    project_name = parser.get("Project", "project_name", fallback="").strip()
    return project_name or None


def sample_project_from_samplesheet(path: Path) -> str | None:
    for filename in ("samplesheet.csv", "samplesheet_bclconvert.csv"):
        samplesheet = path / filename
        if not samplesheet.is_file():
            continue

        current_section: str | None = None
        try:
            with samplesheet.open("r", encoding="utf-8", newline="") as fh:
                for raw_line in fh:
                    row = next(csv.reader([raw_line]))
                    first = row[0].strip() if row else ""
                    if not first:
                        continue
                    if first.startswith("[") and first.endswith("]"):
                        current_section = first[1:-1].strip()
                        continue
                    if current_section not in {"BCLConvert_Data", "Data"}:
                        continue

                    try:
                        project_idx = row.index("Sample_Project")
                    except ValueError:
                        return None

                    for data_line in fh:
                        data_row = next(csv.reader([data_line]))
                        first = data_row[0].strip() if data_row else ""
                        if not first:
                            continue
                        if first.startswith("[") and first.endswith("]"):
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


def _nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def project_id_from_folder(path: Path) -> str | None:
    bpm_meta = load_yaml_file(path / "bpm.meta.yaml")
    project_name = _nested_get(bpm_meta, "export", "demux", "project_name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    export_job_spec = load_json_file(path / "export_job_spec.json")
    project_name = export_job_spec.get("project_name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    project_name = sample_project_from_samplesheet(path)
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    project_name = project_name_from_ini(path)
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    project_meta = load_yaml_file(path / "project.yaml")
    project_name = project_meta.get("name")
    if isinstance(project_name, str) and project_name.strip():
        return project_name.strip()

    return None


def build_run_folder_info(run_id: str, path: Path) -> RunFolderInfo:
    return RunFolderInfo(
        run_id=run_id,
        path=path,
        owner=path_owner(path),
        project_id=project_id_from_folder(path),
    )
