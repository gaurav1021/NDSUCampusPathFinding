from __future__ import annotations

import heapq
import time
from collections import deque
from dataclasses import asdict
from datetime import datetime
from math import asin, cos, inf, radians, sin, sqrt
from typing import Any, Callable

import networkx as nx

from campus_pathfinding.domain.models import AlgorithmRun, EdgeCostBreakdown, UserPreferences, WeatherSnapshot
from campus_pathfinding.services.costs import DynamicCostEngine
from campus_pathfinding.services.explainer import RouteExplainer


class NoRouteFoundError(RuntimeError):
    pass


class CampusRouter:
    def __init__(self, graph: nx.Graph, cost_engine: DynamicCostEngine, explainer: RouteExplainer) -> None:
        self.graph = graph
        self.cost_engine = cost_engine
        self.explainer = explainer

    def heuristic(self, current: str, goal: str) -> float:
        source = self.graph.nodes[current]
        target = self.graph.nodes[goal]
        if source.get("lat") is not None and source.get("lon") is not None and target.get("lat") is not None and target.get("lon") is not None:
            return self._haversine_m(float(source["lat"]), float(source["lon"]), float(target["lat"]), float(target["lon"]))
        dx = float(source["x"]) - float(target["x"])
        dy = float(source["y"]) - float(target["y"])
        return sqrt((dx * dx) + (dy * dy))

    def _haversine_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius_m = 6_371_000.0
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        hav = (sin(d_lat / 2) ** 2) + (cos(lat1_rad) * cos(lat2_rad) * (sin(d_lon / 2) ** 2))
        return 2 * radius_m * asin(sqrt(hav))

    def _edge_cost(
        self,
        source: str,
        target: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> EdgeCostBreakdown:
        return self.cost_engine.edge_cost(
            edge=self.graph.edges[source, target],
            source_node=self.graph.nodes[source],
            target_node=self.graph.nodes[target],
            departure_time=departure_time,
            weather=weather,
            preferences=preferences,
        )

    def _neighbors(
        self,
        node: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> list[tuple[str, EdgeCostBreakdown]]:
        candidates: list[tuple[str, EdgeCostBreakdown]] = []
        for neighbor in self.graph.neighbors(node):
            breakdown = self._edge_cost(node, neighbor, departure_time, weather, preferences)
            if breakdown.is_feasible:
                candidates.append((neighbor, breakdown))
        return candidates

    def _reconstruct_path(self, parents: dict[str, str | None], goal: str) -> list[str]:
        path: list[str] = []
        node: str | None = goal
        while node is not None:
            path.append(node)
            node = parents.get(node)
        path.reverse()
        return path

    def _build_result(
        self,
        algorithm: str,
        path: list[str],
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
        nodes_expanded: int,
        runtime_ms: float,
    ) -> AlgorithmRun:
        edge_breakdowns: list[dict[str, Any]] = []
        total_distance = 0.0
        indoor_distance = 0.0
        outdoor_distance = 0.0
        weather_penalty = 0.0
        accessibility_penalty = 0.0
        safety_penalty = 0.0
        crowd_penalty = 0.0
        total_cost = 0.0

        for left, right in zip(path, path[1:]):
            breakdown = self._edge_cost(left, right, departure_time, weather, preferences)
            edge = self.graph.edges[left, right]
            total_distance += breakdown.distance
            total_cost += breakdown.total_cost
            weather_penalty += breakdown.weather_penalty
            accessibility_penalty += breakdown.accessibility_penalty
            safety_penalty += breakdown.safety_penalty
            crowd_penalty += breakdown.crowd_penalty

            if edge["is_indoor"] or edge["is_tunnel"] or edge["is_skyway"]:
                indoor_distance += breakdown.distance
            elif edge["is_weather_exposed"]:
                outdoor_distance += breakdown.distance

            edge_breakdowns.append(
                {
                    "edge_id": edge["edge_id"],
                    "from": self.graph.nodes[left]["name"],
                    "to": self.graph.nodes[right]["name"],
                    "edge_type": edge["edge_type"],
                    **breakdown.to_dict(),
                }
            )

        path_names = [str(self.graph.nodes[node]["name"]) for node in path]
        result = AlgorithmRun(
            algorithm=algorithm,
            mode="walking",
            path=path,
            path_names=path_names,
            total_cost=round(total_cost, 2),
            distance_m=round(total_distance, 2),
            indoor_distance_m=round(indoor_distance, 2),
            outdoor_distance_m=round(outdoor_distance, 2),
            weather_penalty=round(weather_penalty, 2),
            accessibility_penalty=round(accessibility_penalty, 2),
            safety_penalty=round(safety_penalty, 2),
            crowd_penalty=round(crowd_penalty, 2),
            nodes_expanded=nodes_expanded,
            runtime_ms=round(runtime_ms, 3),
            explanation="",
            edge_breakdowns=edge_breakdowns,
        )
        result.explanation = self.explainer.explain(result, weather, preferences)
        return result

    def run_a_star(
        self,
        start: str,
        goal: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> AlgorithmRun:
        started = time.perf_counter()
        frontier: list[tuple[float, float, str]] = []
        heapq.heappush(frontier, (self.heuristic(start, goal), 0.0, start))
        parents: dict[str, str | None] = {start: None}
        best_cost: dict[str, float] = {start: 0.0}
        visited: set[str] = set()
        expanded = 0

        while frontier:
            _, current_cost, current = heapq.heappop(frontier)
            if current in visited:
                continue
            visited.add(current)
            expanded += 1

            if current == goal:
                runtime_ms = (time.perf_counter() - started) * 1000.0
                return self._build_result("A*", self._reconstruct_path(parents, goal), departure_time, weather, preferences, expanded, runtime_ms)

            for neighbor, breakdown in self._neighbors(current, departure_time, weather, preferences):
                tentative = current_cost + breakdown.total_cost
                if tentative < best_cost.get(neighbor, inf):
                    best_cost[neighbor] = tentative
                    parents[neighbor] = current
                    priority = tentative + self.heuristic(neighbor, goal)
                    heapq.heappush(frontier, (priority, tentative, neighbor))

        raise NoRouteFoundError(f"No feasible A* route found from {start} to {goal}.")

    def run_dijkstra(
        self,
        start: str,
        goal: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> AlgorithmRun:
        started = time.perf_counter()
        frontier: list[tuple[float, str]] = [(0.0, start)]
        parents: dict[str, str | None] = {start: None}
        best_cost: dict[str, float] = {start: 0.0}
        visited: set[str] = set()
        expanded = 0

        while frontier:
            current_cost, current = heapq.heappop(frontier)
            if current in visited:
                continue
            visited.add(current)
            expanded += 1

            if current == goal:
                runtime_ms = (time.perf_counter() - started) * 1000.0
                return self._build_result("Dijkstra", self._reconstruct_path(parents, goal), departure_time, weather, preferences, expanded, runtime_ms)

            for neighbor, breakdown in self._neighbors(current, departure_time, weather, preferences):
                tentative = current_cost + breakdown.total_cost
                if tentative < best_cost.get(neighbor, inf):
                    best_cost[neighbor] = tentative
                    parents[neighbor] = current
                    heapq.heappush(frontier, (tentative, neighbor))

        raise NoRouteFoundError(f"No feasible Dijkstra route found from {start} to {goal}.")

    def run_bfs(
        self,
        start: str,
        goal: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> AlgorithmRun:
        started = time.perf_counter()
        frontier: deque[str] = deque([start])
        parents: dict[str, str | None] = {start: None}
        expanded = 0

        while frontier:
            current = frontier.popleft()
            expanded += 1
            if current == goal:
                runtime_ms = (time.perf_counter() - started) * 1000.0
                return self._build_result("BFS", self._reconstruct_path(parents, goal), departure_time, weather, preferences, expanded, runtime_ms)

            for neighbor, breakdown in self._neighbors(current, departure_time, weather, preferences):
                if breakdown.is_feasible and neighbor not in parents:
                    parents[neighbor] = current
                    frontier.append(neighbor)

        raise NoRouteFoundError(f"No feasible BFS route found from {start} to {goal}.")

    def _weight_function(
        self,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> Callable[[str, str, dict[str, Any]], float]:
        def weight(source: str, target: str, _: dict[str, Any]) -> float:
            return self._edge_cost(source, target, departure_time, weather, preferences).total_cost

        return weight

    def find_alternative_route(
        self,
        start: str,
        goal: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
        primary_path: list[str],
    ) -> AlgorithmRun | None:
        primary_edges = {tuple(sorted(edge)) for edge in zip(primary_path, primary_path[1:])}
        weight = self._weight_function(departure_time, weather, preferences)

        try:
            candidate_paths = nx.shortest_simple_paths(self.graph, start, goal, weight=weight)
            next(candidate_paths)
            for candidate in candidate_paths:
                candidate_edges = {tuple(sorted(edge)) for edge in zip(candidate, candidate[1:])}
                overlap_ratio = 0.0
                if primary_edges:
                    overlap_ratio = len(primary_edges & candidate_edges) / len(primary_edges)
                if overlap_ratio <= 0.75:
                    return self._build_result(
                        "Alternative",
                        candidate,
                        departure_time,
                        weather,
                        preferences,
                        nodes_expanded=len(candidate),
                        runtime_ms=0.0,
                    )
        except (nx.NetworkXNoPath, NoRouteFoundError):
            return None

        return None

    def compare_algorithms(
        self,
        start: str,
        goal: str,
        departure_time: datetime,
        weather: WeatherSnapshot,
        preferences: UserPreferences,
    ) -> list[dict[str, Any]]:
        results = [
            self.run_a_star(start, goal, departure_time, weather, preferences),
            self.run_dijkstra(start, goal, departure_time, weather, preferences),
            self.run_bfs(start, goal, departure_time, weather, preferences),
        ]
        return [asdict(result) for result in results]
