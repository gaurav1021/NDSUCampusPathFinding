from __future__ import annotations

import sys
from datetime import date, datetime, time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from campus_pathfinding.domain.models import OptimizationProfile, UserPreferences, WeatherMode
from campus_pathfinding.services.planner import get_planner
from campus_pathfinding.services.router import NoRouteFoundError


planner = get_planner()


def _location_label_map() -> dict[str, str]:
    return {item.node_id: item.name for item in planner.get_locations()}


def _route_edge_set(path: list[str]) -> set[tuple[str, str]]:
    return {tuple(sorted((left, right))) for left, right in zip(path, path[1:])}


def _plot_graph(primary_path: list[str], alternative_path: list[str] | None) -> go.Figure:
    payload = planner.graph_payload()
    nodes = {node["node_id"]: node for node in payload["nodes"]}
    edges = payload["edges"]
    use_geo = all(node.get("lat") is not None and node.get("lon") is not None for node in payload["nodes"])

    primary_edges = _route_edge_set(primary_path)
    alternative_edges = _route_edge_set(alternative_path or [])

    figure = go.Figure()

    for edge in edges:
        source = nodes[edge["source"]]
        target = nodes[edge["target"]]
        edge_key = tuple(sorted((edge["source"], edge["target"])))

        color = "#b7c0ca"
        width = 2
        dash = "solid"
        if edge_key in alternative_edges:
            color = "#f4a261"
            width = 4
            dash = "dash"
        if edge_key in primary_edges:
            color = "#e63946"
            width = 5
            dash = "solid"

        x_values = [source["lon"], target["lon"]] if use_geo else [source["x"], target["x"]]
        y_values = [source["lat"], target["lat"]] if use_geo else [source["y"], target["y"]]

        if use_geo:
            figure.add_trace(
                go.Scattermapbox(
                    lon=x_values,
                    lat=y_values,
                    mode="lines",
                    line={"color": color, "width": width},
                    hoverinfo="text",
                    text=f"{source['name']} -> {target['name']} ({edge['edge_type']}, {edge['distance_m']} m)",
                    showlegend=False,
                )
            )
        else:
            figure.add_trace(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    line={"color": color, "width": width, "dash": dash},
                    hoverinfo="text",
                    text=f"{source['name']} -> {target['name']} ({edge['edge_type']}, {edge['distance_m']} m)",
                    showlegend=False,
                )
            )

    building_nodes = [node for node in payload["nodes"] if node["selectable"]]
    other_nodes = [node for node in payload["nodes"] if not node["selectable"]]

    if use_geo:
        figure.add_trace(
            go.Scattermapbox(
                lon=[node["lon"] for node in other_nodes],
                lat=[node["lat"] for node in other_nodes],
                mode="markers",
                marker={"size": 10, "color": "#457b9d"},
                text=[node["name"] for node in other_nodes],
                hovertemplate="%{text}<extra></extra>",
                name="Campus connectors",
            )
        )
        figure.add_trace(
            go.Scattermapbox(
                lon=[node["lon"] for node in building_nodes],
                lat=[node["lat"] for node in building_nodes],
                mode="markers+text",
                marker={"size": 15, "color": "#1d3557"},
                text=[node["name"] for node in building_nodes],
                textposition="top center",
                hovertemplate="%{text}<extra></extra>",
                name="Selectable buildings",
            )
        )
    else:
        figure.add_trace(
            go.Scatter(
                x=[node["x"] for node in other_nodes],
                y=[node["y"] for node in other_nodes],
                mode="markers",
                marker={"size": 10, "color": "#457b9d"},
                text=[node["name"] for node in other_nodes],
                hovertemplate="%{text}<extra></extra>",
                name="Campus connectors",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[node["x"] for node in building_nodes],
                y=[node["y"] for node in building_nodes],
                mode="markers+text",
                marker={"size": 15, "color": "#1d3557", "line": {"color": "#f1faee", "width": 2}},
                text=[node["name"] for node in building_nodes],
                textposition="top center",
                hovertemplate="%{text}<extra></extra>",
                name="Selectable buildings",
            )
        )

    if use_geo:
        figure.update_layout(
            mapbox={"style": "open-street-map", "center": {"lat": 46.8925, "lon": -96.8015}, "zoom": 15.1},
            paper_bgcolor="#f8f9fb",
            title="Expanded NDSU Main Campus Graph with MATBUS-Aware Anchors",
            legend={"orientation": "h", "y": 1.02, "x": 0.0},
            margin={"l": 10, "r": 10, "t": 60, "b": 10},
            height=640,
        )
    else:
        figure.update_layout(
            paper_bgcolor="#f8f9fb",
            plot_bgcolor="#f8f9fb",
            title="Expanded NDSU Main Campus Graph with MATBUS-Aware Anchors",
            xaxis={"visible": False},
            yaxis={"visible": False},
            legend={"orientation": "h", "y": 1.02, "x": 0.0},
            margin={"l": 10, "r": 10, "t": 60, "b": 10},
            height=640,
        )
    return figure


st.set_page_config(page_title="Climate-Aware NDSU Path Planning", layout="wide")
st.title("Climate-Aware Intelligent Path Planning for Smart Campus Navigation Using A* Search")
st.caption("Graduate-level AI research demo for NDSU smart campus routing under weather, accessibility, safety, and building-availability constraints.")

locations = _location_label_map()
location_ids = list(locations.keys())
scenario_lookup = {item.key: item for item in planner.get_scenarios()}

with st.sidebar:
    st.header("Route Controls")
    start = st.selectbox("Start location", location_ids, format_func=lambda value: locations[value], index=0)
    destination = st.selectbox("Destination", location_ids, format_func=lambda value: locations[value], index=min(1, len(location_ids) - 1))

    profile = st.selectbox(
        "Optimization objective",
        [profile.value for profile in OptimizationProfile],
        format_func=lambda value: value.replace("_", " ").title(),
    )
    weather_mode = st.radio("Weather source", [WeatherMode.SCENARIO.value, WeatherMode.LIVE.value], horizontal=True)
    scenario_name = st.selectbox("Scenario", list(scenario_lookup.keys()), format_func=lambda value: scenario_lookup[value].label)

    selected_date = st.date_input("Departure date", value=date.today())
    selected_time = st.time_input("Departure time", value=time(13, 30))
    departure = datetime.combine(selected_date, selected_time)

    wheelchair_required = st.checkbox("Wheelchair accessible route", value=profile == OptimizationProfile.WHEELCHAIR_ACCESSIBLE.value)
    avoid_stairs = st.checkbox("Avoid stairs", value=profile in {OptimizationProfile.WHEELCHAIR_ACCESSIBLE.value, OptimizationProfile.WINTER_SAFE.value})
    prefer_indoor = st.checkbox("Indoor path preference", value=profile in {OptimizationProfile.INDOOR_PREFERRED.value, OptimizationProfile.WINTER_SAFE.value})
    prefer_well_lit = st.checkbox("Well-lit path preference", value=profile == OptimizationProfile.SAFEST_AT_NIGHT.value)
    winter_safety_mode = st.checkbox("Winter-safe routing", value=profile == OptimizationProfile.WINTER_SAFE.value)
    allow_transit = st.checkbox("Allow MATBUS transit", value=True)
    prefer_transit = st.checkbox("Prefer transit when helpful", value=False)
    crowd_avoidance = st.slider("Crowd avoidance weight", 0.0, 1.0, 0.5, 0.1)

    run_query = st.button("Compute route", use_container_width=True)

if run_query:
    preferences = UserPreferences(
        optimization_profile=OptimizationProfile(profile),
        wheelchair_required=wheelchair_required,
        avoid_stairs=avoid_stairs,
        prefer_indoor=prefer_indoor,
        prefer_well_lit=prefer_well_lit,
        winter_safety_mode=winter_safety_mode,
        allow_transit=allow_transit,
        prefer_transit=prefer_transit,
        crowd_avoidance=crowd_avoidance,
    ).normalized()

    try:
        result = planner.plan_route(
            start=start,
            destination=destination,
            departure_time=departure,
            weather_mode=WeatherMode(weather_mode),
            preferences=preferences,
            scenario_name=scenario_name,
        )
    except NoRouteFoundError as exc:
        st.error(str(exc))
    else:
        recommended = result.recommended_route
        alternative = result.alternative_route
        transit_option = result.transit_option

        metric_columns = st.columns(4)
        metric_columns[0].metric("Walking route cost", f"{recommended.total_cost:.1f}")
        metric_columns[1].metric("Distance", f"{recommended.distance_m:.0f} m")
        metric_columns[2].metric("Indoor distance", f"{recommended.indoor_distance_m:.0f} m")
        metric_columns[3].metric("Outdoor distance", f"{recommended.outdoor_distance_m:.0f} m")

        left, right = st.columns([1.15, 1])
        with left:
            st.plotly_chart(_plot_graph(recommended.path, alternative.path if alternative else None), use_container_width=True)
        with right:
            st.subheader("Route explanation")
            st.write(recommended.explanation)
            st.subheader("Best mode")
            st.write(result.best_mode.replace("_", " ").title())
            st.subheader("Recommended path")
            st.write(" -> ".join(recommended.path_names))
            if alternative:
                st.subheader("Alternative path")
                st.write(" -> ".join(alternative.path_names))
            if transit_option:
                st.subheader("MATBUS option")
                st.write(transit_option.route_summary)
                st.write(transit_option.explanation)
                st.caption(f"Estimated duration: {transit_option.estimated_duration_min:.1f} min | Walking: {transit_option.walking_distance_m:.0f} m | Live data used: {transit_option.live_data_used}")

            st.subheader("Weather snapshot")
            st.json(result.weather)

        comparison_frame = pd.DataFrame(result.algorithm_comparison)[
            ["algorithm", "total_cost", "distance_m", "outdoor_distance_m", "nodes_expanded", "runtime_ms"]
        ].sort_values(by="runtime_ms")
        st.subheader("Algorithm comparison")
        st.dataframe(comparison_frame, use_container_width=True)

        edge_frame = pd.DataFrame(recommended.edge_breakdowns)
        st.subheader("Edge-level cost breakdown")
        st.dataframe(edge_frame, use_container_width=True)
else:
    st.info("Select an origin, destination, and routing preference profile, then compute a route.")
