from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


BOOLEAN_COLUMNS = {
    "is_indoor",
    "is_accessible",
    "has_elevator",
    "has_door_operator",
    "has_emergency_phone",
    "well_lit",
    "selectable",
    "has_stairs",
    "is_tunnel",
    "is_skyway",
    "is_weather_exposed",
    "bidirectional",
}


def _coerce_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    for column in BOOLEAN_COLUMNS.intersection(frame.columns):
        frame[column] = frame[column].map(_coerce_boolean)
    return frame


def load_nodes(path: Path) -> pd.DataFrame:
    nodes = pd.read_csv(path)
    return _normalize_frame(nodes)


def load_edges(path: Path) -> pd.DataFrame:
    edges = pd.read_csv(path)
    return _normalize_frame(edges)


def load_scenarios(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return _normalize_frame(frame)
