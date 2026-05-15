from __future__ import annotations

from fastapi import FastAPI, HTTPException

from campus_pathfinding.config import get_settings
from campus_pathfinding.domain.models import RouteRequestModel, preferences_from_request
from campus_pathfinding.services.planner import get_planner
from campus_pathfinding.services.router import NoRouteFoundError


settings = get_settings()
planner = get_planner()

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="Climate-aware smart campus path planning for NDSU using A* search.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/locations")
def locations() -> list[dict[str, str]]:
    return [item.model_dump() for item in planner.get_locations()]


@app.get("/scenarios")
def scenarios() -> list[dict[str, str | float | bool]]:
    return [item.model_dump() for item in planner.get_scenarios()]


@app.get("/graph")
def graph() -> dict[str, object]:
    return planner.graph_payload()


@app.post("/route")
def route(request: RouteRequestModel) -> dict[str, object]:
    try:
        recommendation = planner.plan_route(
            start=request.start,
            destination=request.destination,
            departure_time=request.departure_time,
            weather_mode=request.weather_mode,
            preferences=preferences_from_request(request),
            scenario_name=request.scenario_name,
        )
        return recommendation.to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown routing entity: {exc}") from exc
    except NoRouteFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
