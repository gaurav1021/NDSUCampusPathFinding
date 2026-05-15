from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "Climate-Aware Intelligent Path Planning for Smart Campus Navigation Using A* Search"
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    nodes_file: str = "ndsu_nodes_extended.csv"
    edges_file: str = "ndsu_edges_extended.csv"
    scenarios_file: str = "scenario_profiles.json"
    matbus_stop_links_file: str = "matbus_stop_links.csv"
    matbus_gtfs_dir: Path = Field(default_factory=lambda: Path("data") / "matbus_gtfs")
    matbus_gtfs_zip_path: Path = Field(default_factory=lambda: Path("data") / "matbus_gtfs.zip")
    matbus_gtfs_static_url: str = "https://ridematbus.com/gtfs"
    matbus_gtfs_vehicle_positions_url: str | None = None
    matbus_gtfs_trip_updates_url: str | None = None
    matbus_gtfs_alerts_url: str | None = None
    ndsu_campus_lat: float = 46.8917
    ndsu_campus_lon: float = -96.8037
    openweather_api_key: str | None = None
    openweather_base_url: str = "https://api.openweathermap.org/data/2.5/weather"
    default_scenario: str = "winter_storm"

    @property
    def nodes_path(self) -> Path:
        return self.data_dir / self.nodes_file

    @property
    def edges_path(self) -> Path:
        return self.data_dir / self.edges_file

    @property
    def scenarios_path(self) -> Path:
        return self.data_dir / self.scenarios_file

    @property
    def matbus_stop_links_path(self) -> Path:
        return self.data_dir / self.matbus_stop_links_file


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
