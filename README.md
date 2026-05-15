# Climate-Aware Intelligent Path Planning for Smart Campus Navigation Using A* Search

This project implements a research-oriented smart campus navigation system for North Dakota State University (NDSU). Instead of recommending only the shortest path, the system finds the best route under weather exposure, indoor connectivity, accessibility, nighttime safety, building operating hours, crowd-aware penalties, and optional MATBUS transit. The core walking planner uses A* search and compares its behavior against Dijkstra and BFS baselines, while the transit layer evaluates official MATBUS GTFS service as a multimodal option.

The implementation is designed as a graduate-level AI project for CS 724 and includes a reusable routing engine, an API service, a Streamlit interface, benchmarking scripts, tests, and research deliverables.

## Research Motivation

NDSU campus maps explicitly surface mobility and accessibility infrastructure such as elevators, door operators, emergency telephones, and tunnels/skyways. That makes NDSU a strong smart-campus routing case, especially in Fargo winter conditions. This repository now uses an **expanded main-campus graph with official-structure-backed naming and MATBUS stop anchors**, plus the official public MATBUS GTFS feed for campus transit service. It is still not a full university GIS export, but it is materially closer to the official campus footprint than the original central-core mock.

## Core Idea

The campus is represented as a weighted graph:

`G = (V, E)`

- `V`: buildings, entrances, intersections, and indoor connector access points
- `E`: sidewalks, tunnels, skyways, indoor corridors, and entry transitions

Each edge receives a dynamic cost:

`Cost = Distance + WeatherPenalty + AccessibilityPenalty + SafetyPenalty + CrowdPenalty`

The planner changes route recommendations according to:

- distance
- indoor versus outdoor exposure
- snow, rain, wind, and wind chill
- building open/close windows
- tunnel and skyway availability
- wheelchair accessibility and stairs avoidance
- nighttime lighting/safety preference
- crowd penalties
- MATBUS campus-route availability and stop access

## Project Structure

```text
CampusPathFinding/
|-- app/
|   `-- streamlit_app.py
|-- data/
|   |-- matbus_gtfs/
|   |-- matbus_gtfs.zip
|   |-- matbus_stop_links.csv
|   |-- ndsu_edges_extended.csv
|   |-- ndsu_nodes_extended.csv
|   `-- scenario_profiles.json
|-- docs/
|   |-- final_presentation.md
|   |-- proposal_presentation.md
|   `-- report_outline.md
|-- scripts/
|   |-- compare_seasons.py
|   |-- evaluate_algorithms.py
|   |-- refresh_matbus_gtfs.py
|   `-- run_api.py
|-- src/campus_pathfinding/
|   |-- api/main.py
|   |-- config.py
|   |-- data/loader.py
|   |-- domain/models.py
|   `-- services/
|       |-- costs.py
|       |-- explainer.py
|       |-- gtfs.py
|       |-- graph_builder.py
|       |-- planner.py
|       |-- router.py
|       |-- transit.py
|       `-- weather.py
|-- tests/
|   |-- test_api.py
|   `-- test_router.py
|-- .env.example
|-- pyproject.toml
|-- README.md
`-- requirements.txt
```

## System Architecture

### 1. Data Layer

- `ndsu_nodes_extended.csv`: expanded NDSU main-campus and downtown-campus building graph with map coordinates
- `ndsu_edges_extended.csv`: sidewalks, skyways, tunnels, doorways, and stair-sensitive edges
- `matbus_gtfs/`: official MATBUS GTFS static feed extracted from `https://ridematbus.com/gtfs`
- `matbus_stop_links.csv`: building-to-stop walk access mappings for multimodal routing
- `scenario_profiles.json`: deterministic weather scenarios for experiments

### 2. Dynamic Cost Engine

The cost engine computes per-edge penalties using:

- exposed-edge weather severity
- profile-sensitive accessibility penalties
- lighting penalties for night travel
- time-of-day crowd penalties
- feasibility checks for building and connector hours

### 3. Search Algorithms

- **A\***: main intelligent routing method with Euclidean heuristic
- **Dijkstra**: optimal weighted baseline without heuristic guidance
- **BFS**: unweighted baseline using hop count

### 4. Service Layer

- `CampusPlanner`: orchestrates graph loading, weather resolution, routing, and comparison
- `WeatherService`: uses OpenWeather live data when configured and falls back to scenario simulation
- `RouteExplainer`: generates human-readable route selection rationale

### 5. Interfaces

- **FastAPI backend** for machine-readable planning
- **Streamlit frontend** for interactive route experimentation and visualization
- **MATBUS multimodal option** based on official GTFS routes 13, 31, 33, and 34

## Heuristic Design

The A* heuristic is straight-line Euclidean distance between node coordinates in the campus graph. This is admissible because the edge-cost function adds only nonnegative penalties to physical distance, so the direct spatial distance remains a lower bound on true route cost.

## Research Evaluation Plan

The included benchmarking scripts support:

- A* versus Dijkstra versus BFS comparison
- weather scenario simulation
- winter versus summer route comparison
- analysis of runtime, nodes expanded, route cost, and outdoor exposure

Suggested primary metrics:

- total route cost
- physical distance
- outdoor distance
- nodes expanded
- runtime in milliseconds
- accessibility compliance
- alternative route diversity

## Installation

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

If you want live weather, add an `.env` file based on `.env.example` and provide an OpenWeather API key.

## Running the Backend

```bash
python scripts/run_api.py
```

FastAPI endpoints:

- `GET /health`
- `GET /locations`
- `GET /scenarios`
- `GET /graph`
- `POST /route`

Example request:

```json
{
  "start": "mu_interior",
  "destination": "ladd_interior",
  "weather_mode": "scenario",
  "scenario_name": "winter_storm",
  "optimization_profile": "winter_safe"
}
```

## Running the Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

The UI supports:

- start and destination building selection
- optimization objective selection
- scenario or live weather mode
- wheelchair, indoor, well-lit, and winter-safe preferences
- graph visualization with recommended and alternative routes

## Running Experiments

Benchmark all algorithms:

```bash
python scripts/evaluate_algorithms.py
```

Refresh the official MATBUS GTFS feed:

```bash
python scripts/refresh_matbus_gtfs.py
```

Compare summer versus winter routing:

```bash
python scripts/compare_seasons.py
```

Outputs are written to `outputs/`.

## Running Tests

```bash
pytest
```

## Example Research Findings to Highlight

- In winter-storm scenarios, A* shifts heavily toward the Memorial Union-Sugihara-Ladd climate-controlled corridor.
- Wheelchair routing avoids the shorter stairs-based Library-Minard cut-through and selects an accessible outdoor alternative.
- Night-safety preferences penalize poorly lit shortcuts even when they are slightly shorter.
- A* should expand fewer nodes than Dijkstra while preserving route quality under the same weighted model.

## Limitations

- The building graph is still a research abstraction, not an official facilities GIS export or authoritative pedestrian network.
- Crowd effects are simulated rather than measured from live foot-traffic sensors.
- Building hours outside Memorial Union are representative academic schedules and should be replaced with official feeds for deployment.
- MATBUS live GTFS-realtime endpoints are supported as configuration hooks, but MATBUS does not publish the public protobuf URLs on the static GTFS page, so schedule-based GTFS is the default out of the box.

## Future Extensions

- GIS-backed campus geometry
- live building-hours integration
- MATBUS and parking integration
- direct GTFS-realtime protobuf integration once public endpoint URLs are confirmed
- forecast-based route prediction
- learned congestion estimation with scikit-learn
- multi-objective path recommendation

## References

- NDSU Campus Maps: https://www.ndsu.edu/facilities/campusmaps
- NDSU Buildings Index: https://www.ndsu.edu/alphaindex/buildings
- Memorial Union hours: https://www.ndsu.edu/mu
- NDSU Skyways and Connection Plaza: https://zerrbergarchitects.com/project/ndsu-skyways-and-connection-plaza/
