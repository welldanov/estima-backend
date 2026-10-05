import json
from pathlib import Path
from typing import Any


def collect_json_files(
        path: Path,
) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".json":
            raise ValueError(
                f"Expected JSON file: {path}"
            )

        return [path]

    if path.is_dir():
        files = sorted(path.rglob("*.json"))

        if not files:
            raise ValueError(
                f"No JSON files found in: {path}"
            )

        return files

    raise FileNotFoundError(
        f"Path does not exist: {path}"
    )


def read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"JSON file does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Expected file, got: {path}"
        )

    try:
        with path.open(
                "r",
                encoding="utf-8",
        ) as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: "
            f"line={exc.lineno}, column={exc.colno}"
        ) from exc


def extract_records(data: Any) -> list[dict]:
    if isinstance(data, list):
        records = data

    elif isinstance(data, dict):
        if "items" in data:
            records = data["items"]
        elif "id" in data:
            records = [data]
        else:
            records = []

    else:
        raise ValueError(
            "JSON root must be an object or an array"
        )

    if not all(isinstance(item, dict) for item in records):
        raise ValueError(
            "Every JSON record must be an object"
        )

    return records
