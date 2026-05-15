from __future__ import annotations

from typing import Any

import httpx

from campus_pathfinding.config import Settings
from campus_pathfinding.domain.models import WeatherSnapshot


class WeatherService:
    def __init__(self, settings: Settings, scenarios: dict[str, Any]) -> None:
        self.settings = settings
        self.scenarios = scenarios

    def get_scenario_weather(self, scenario_name: str) -> WeatherSnapshot:
        payload = self.scenarios[scenario_name]
        return WeatherSnapshot(source=f"scenario:{scenario_name}", **{k: payload[k] for k in payload if k not in {"label", "description"}})

    def get_live_weather(self) -> WeatherSnapshot:
        if not self.settings.openweather_api_key:
            return self.get_scenario_weather(self.settings.default_scenario)

        params = {
            "lat": self.settings.ndsu_campus_lat,
            "lon": self.settings.ndsu_campus_lon,
            "appid": self.settings.openweather_api_key,
            "units": "metric",
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(self.settings.openweather_base_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return self.get_scenario_weather(self.settings.default_scenario)

        weather_block = payload.get("weather", [{}])[0]
        main_block = payload.get("main", {})
        wind_block = payload.get("wind", {})
        rain_block = payload.get("rain", {})
        snow_block = payload.get("snow", {})
        system_block = payload.get("sys", {})

        current_epoch = payload.get("dt", 0)
        sunrise_epoch = system_block.get("sunrise", 0)
        sunset_epoch = system_block.get("sunset", 0)
        is_night = bool(current_epoch and sunrise_epoch and sunset_epoch and not (sunrise_epoch <= current_epoch <= sunset_epoch))

        temp_c = float(main_block.get("temp", 0.0))
        feels_like_c = float(main_block.get("feels_like", temp_c))
        wind_speed = float(wind_block.get("speed", 0.0))

        return WeatherSnapshot(
            source="openweather",
            condition=str(weather_block.get("main", "clear")).lower(),
            temp_c=temp_c,
            feels_like_c=feels_like_c,
            wind_speed_mps=wind_speed,
            rain_mm=float(rain_block.get("1h", 0.0) or 0.0),
            snow_mm=float(snow_block.get("1h", 0.0) or 0.0),
            wind_chill_c=min(temp_c, feels_like_c),
            is_night=is_night,
        )
