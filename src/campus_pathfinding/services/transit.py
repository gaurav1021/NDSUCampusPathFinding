from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx
import networkx as nx
import pandas as pd

from campus_pathfinding.config import Settings
from campus_pathfinding.domain.models import TransitLeg, TransitRecommendation, UserPreferences
from campus_pathfinding.services.gtfs import MatbusStaticFeed, minutes_to_clock, parse_gtfs_time_to_minutes


class MatbusTransitService:
    def __init__(
        self,
        settings: Settings,
        graph: nx.Graph,
        stop_links: pd.DataFrame,
        static_feed: MatbusStaticFeed | None,
    ) -> None:
        self.settings = settings
        self.graph = graph
        self.stop_links = stop_links
        self.static_feed = static_feed

    def has_static_feed(self) -> bool:
        return self.static_feed is not None

    def _distance_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_m = 6_371_000.0
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        hav = (sin(d_lat / 2) ** 2) + (cos(lat1_rad) * cos(lat2_rad) * (sin(d_lon / 2) ** 2))
        return 2 * radius_m * asin(sqrt(hav))

    def _nearest_stops(self, node_id: str, limit: int = 10) -> pd.DataFrame:
        if self.static_feed is None:
            return pd.DataFrame()

        node = self.graph.nodes[node_id]
        if node.get("lat") is None or node.get("lon") is None:
            linked = self.stop_links[self.stop_links["node_id"] == node_id]
            return linked.merge(self.static_feed.stops, on="stop_id", how="left").head(limit)

        stops = self.static_feed.stops.copy()
        stops["distance_m"] = stops.apply(
            lambda row: self._distance_m(float(node["lat"]), float(node["lon"]), float(row["stop_lat"]), float(row["stop_lon"])),
            axis=1,
        )
        linked = self.stop_links[self.stop_links["node_id"] == node_id].merge(self.static_feed.stops, on="stop_id", how="left")
        if not linked.empty and "distance_m" not in linked.columns:
            linked["distance_m"] = linked["walking_distance_m"]

        nearby = stops.sort_values("distance_m").head(limit * 2)
        combined = pd.concat([linked, nearby], ignore_index=True, sort=False)
        combined["stop_id"] = combined["stop_id"].astype(str)
        combined = combined.sort_values("distance_m").drop_duplicates(subset=["stop_id"])
        return combined.head(limit)

    def _node_walk_distance_to_stop(self, node_id: str, stop_id: str) -> float:
        linked = self.stop_links[(self.stop_links["node_id"] == node_id) & (self.stop_links["stop_id"].astype(str) == str(stop_id))]
        if not linked.empty:
            return float(linked.iloc[0]["walking_distance_m"])

        node = self.graph.nodes[node_id]
        if node.get("lat") is None or node.get("lon") is None or self.static_feed is None:
            return 250.0

        stop = self.static_feed.stops[self.static_feed.stops["stop_id"].astype(str) == str(stop_id)].iloc[0]
        return self._distance_m(float(node["lat"]), float(node["lon"]), float(stop["stop_lat"]), float(stop["stop_lon"]))

    def _live_data_available(self) -> bool:
        urls = [
            self.settings.matbus_gtfs_vehicle_positions_url,
            self.settings.matbus_gtfs_trip_updates_url,
            self.settings.matbus_gtfs_alerts_url,
        ]
        return any(urls)

    def _probe_live_endpoint(self) -> bool:
        urls = [
            self.settings.matbus_gtfs_vehicle_positions_url,
            self.settings.matbus_gtfs_trip_updates_url,
            self.settings.matbus_gtfs_alerts_url,
        ]
        for url in urls:
            if not url:
                continue
            try:
                with httpx.Client(timeout=6.0) as client:
                    response = client.get(url)
                    if response.status_code == 200:
                        return True
            except Exception:
                continue
        return False

    def find_transit_option(
        self,
        start_node_id: str,
        destination_node_id: str,
        departure_time: datetime,
        preferences: UserPreferences,
    ) -> TransitRecommendation | None:
        if self.static_feed is None or not preferences.allow_transit:
            return None

        origin_stops = self._nearest_stops(start_node_id)
        destination_stops = self._nearest_stops(destination_node_id)
        if origin_stops.empty or destination_stops.empty:
            return None

        relevant_routes = self.static_feed.relevant_routes()
        active_service_ids = self.static_feed.active_service_ids(departure_time.date())
        trips = self.static_feed.trips[
            (self.static_feed.trips["route_id"].isin(relevant_routes["route_id"]))
            & (self.static_feed.trips["service_id"].astype(str).isin(active_service_ids))
        ]
        if trips.empty:
            return None

        stop_times = self.static_feed.stop_times.copy()
        stop_times["stop_id"] = stop_times["stop_id"].astype(str)
        stop_times["arrival_minutes"] = stop_times["arrival_time"].map(parse_gtfs_time_to_minutes)
        stop_times["departure_minutes"] = stop_times["departure_time"].map(parse_gtfs_time_to_minutes)

        candidate_rows: list[dict[str, Any]] = []
        requested_minutes = departure_time.hour * 60 + departure_time.minute
        stops_lookup = self.static_feed.stops[["stop_id", "stop_name"]].copy()
        stops_lookup["stop_id"] = stops_lookup["stop_id"].astype(str)

        for trip_id, trip_group in stop_times[stop_times["trip_id"].isin(trips["trip_id"])].groupby("trip_id"):
            ordered = trip_group.sort_values("stop_sequence")
            for _, board in ordered[ordered["stop_id"].isin(origin_stops["stop_id"])].iterrows():
                walk_to_stop_m = self._node_walk_distance_to_stop(start_node_id, str(board["stop_id"]))
                walk_to_stop_min = walk_to_stop_m / 80.0
                earliest_board_min = requested_minutes + walk_to_stop_min

                if float(board["departure_minutes"]) < earliest_board_min:
                    continue

                downstream = ordered[(ordered["stop_sequence"] > board["stop_sequence"]) & (ordered["stop_id"].isin(destination_stops["stop_id"]))]
                for _, alight in downstream.iterrows():
                    walk_from_stop_m = self._node_walk_distance_to_stop(destination_node_id, str(alight["stop_id"]))
                    walk_from_stop_min = walk_from_stop_m / 80.0
                    wait_min = float(board["departure_minutes"]) - requested_minutes - walk_to_stop_min
                    ride_min = float(alight["arrival_minutes"]) - float(board["departure_minutes"])
                    if ride_min < 0:
                        continue

                    generalized_cost = (
                        walk_to_stop_m
                        + walk_from_stop_m
                        + max(0.0, wait_min) * 55.0
                        + ride_min * 18.0
                        + (20.0 if preferences.prefer_indoor else 0.0)
                    )

                    candidate_rows.append(
                        {
                            "trip_id": trip_id,
                            "board_stop_id": str(board["stop_id"]),
                            "alight_stop_id": str(alight["stop_id"]),
                            "walk_to_stop_m": walk_to_stop_m,
                            "walk_from_stop_m": walk_from_stop_m,
                            "walk_time_min": walk_to_stop_min + walk_from_stop_min,
                            "wait_min": max(0.0, wait_min),
                            "ride_min": ride_min,
                            "total_min": walk_to_stop_min + max(0.0, wait_min) + ride_min + walk_from_stop_min,
                            "generalized_cost": generalized_cost,
                        }
                    )

        if not candidate_rows:
            return None

        candidate_frame = pd.DataFrame(candidate_rows).sort_values(["generalized_cost", "total_min"])
        best = candidate_frame.iloc[0]
        trip = trips[trips["trip_id"] == best["trip_id"]].iloc[0]
        route = relevant_routes[relevant_routes["route_id"] == trip["route_id"]].iloc[0]
        board_stop = stops_lookup[stops_lookup["stop_id"].astype(str) == best["board_stop_id"]].iloc[0]
        alight_stop = stops_lookup[stops_lookup["stop_id"].astype(str) == best["alight_stop_id"]].iloc[0]

        live_data_used = self._probe_live_endpoint() if self._live_data_available() else False
        route_summary = f"Route {str(route['route_short_name']).strip()} from {board_stop['stop_name']} to {alight_stop['stop_name']}"
        explanation = (
            f"This MATBUS option uses {route_summary}. "
            f"It reduces exposed walking to about {best['walk_to_stop_m'] + best['walk_from_stop_m']:.0f} meters "
            f"with an estimated wait of {best['wait_min']:.1f} minutes and ride time of {best['ride_min']:.1f} minutes."
        )

        leg = TransitLeg(
            route_id=str(route["route_id"]),
            route_short_name=str(route["route_short_name"]).strip(),
            route_long_name=str(route["route_long_name"]),
            board_stop_id=str(best["board_stop_id"]),
            board_stop_name=str(board_stop["stop_name"]),
            alight_stop_id=str(best["alight_stop_id"]),
            alight_stop_name=str(alight_stop["stop_name"]),
            departure_time=minutes_to_clock(int(round(requested_minutes + best["walk_time_min"] / 2 + best["wait_min"]))),
            arrival_time=minutes_to_clock(int(round(requested_minutes + best["total_min"]))),
            wait_minutes=round(float(best["wait_min"]), 2),
            ride_minutes=round(float(best["ride_min"]), 2),
        )

        return TransitRecommendation(
            mode="transit",
            total_cost=round(float(best["generalized_cost"]), 2),
            estimated_duration_min=round(float(best["total_min"]), 2),
            walking_distance_m=round(float(best["walk_to_stop_m"] + best["walk_from_stop_m"]), 2),
            walking_time_min=round(float(best["walk_time_min"]), 2),
            wait_time_min=round(float(best["wait_min"]), 2),
            in_vehicle_time_min=round(float(best["ride_min"]), 2),
            transfers=0,
            route_summary=route_summary,
            explanation=explanation,
            live_data_used=live_data_used,
            path_names=[
                self.graph.nodes[start_node_id]["name"],
                str(board_stop["stop_name"]),
                f"Route {str(route['route_short_name']).strip()}",
                str(alight_stop["stop_name"]),
                self.graph.nodes[destination_node_id]["name"],
            ],
            legs=[leg],
        )

    def as_dict(self, recommendation: TransitRecommendation | None) -> dict[str, Any] | None:
        if recommendation is None:
            return None
        return asdict(recommendation)
