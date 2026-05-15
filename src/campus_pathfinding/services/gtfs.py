from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


def parse_gtfs_time_to_minutes(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    return (int(hours) * 60) + int(minutes) + round(int(seconds) / 60)


def minutes_to_clock(minutes: int) -> str:
    normalized = minutes % (24 * 60)
    hours = normalized // 60
    mins = normalized % 60
    return f"{hours:02d}:{mins:02d}"


def service_active(calendar_row: pd.Series, service_date: date) -> bool:
    if service_date.strftime("%Y%m%d") < str(calendar_row["start_date"]):
        return False
    if service_date.strftime("%Y%m%d") > str(calendar_row["end_date"]):
        return False
    weekday_column = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ][service_date.weekday()]
    return bool(int(calendar_row[weekday_column]))


@dataclass(slots=True)
class MatbusStaticFeed:
    routes: pd.DataFrame
    trips: pd.DataFrame
    stop_times: pd.DataFrame
    stops: pd.DataFrame
    calendar: pd.DataFrame

    @classmethod
    def from_directory(cls, path: Path) -> "MatbusStaticFeed":
        return cls(
            routes=pd.read_csv(path / "routes.txt"),
            trips=pd.read_csv(path / "trips.txt"),
            stop_times=pd.read_csv(path / "stop_times.txt"),
            stops=pd.read_csv(path / "stops.txt"),
            calendar=pd.read_csv(path / "calendar.txt"),
        )

    def relevant_routes(self, route_names: tuple[str, ...] = ("13", "31", "33", "34")) -> pd.DataFrame:
        routes = self.routes.copy()
        routes["route_short_name"] = routes["route_short_name"].astype(str).str.strip()
        return routes[routes["route_short_name"].isin(route_names)]

    def active_service_ids(self, service_date: date) -> set[str]:
        active = self.calendar[self.calendar.apply(lambda row: service_active(row, service_date), axis=1)]
        return set(active["service_id"].astype(str))

