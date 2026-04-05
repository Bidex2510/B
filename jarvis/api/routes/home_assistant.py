"""Home Assistant API routes - real smart home control."""

import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

HA_URL = os.getenv("HOME_ASSISTANT_URL", "")  # e.g. http://192.168.1.100:8123
HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")


def _headers():
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}


def _check_auth():
    if not HA_URL or not HA_TOKEN:
        return {
            "status": "config_needed",
            "message": "Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN in your .env file.",
            "setup_steps": [
                "1. Install Home Assistant: https://www.home-assistant.io/installation/",
                "2. Go to Profile > Long-Lived Access Tokens",
                "3. Create a token and set it as HOME_ASSISTANT_TOKEN",
                "4. Set HOME_ASSISTANT_URL to your HA instance URL",
            ],
        }
    return None


@router.get("/states")
async def get_all_states():
    """Get all device states from Home Assistant."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HA_URL}/api/states", headers=_headers())
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to get states")
    entities = []
    for e in resp.json():
        entities.append({
            "entity_id": e["entity_id"],
            "state": e["state"],
            "friendly_name": e.get("attributes", {}).get("friendly_name", e["entity_id"]),
        })
    return {"entities": entities}


@router.get("/state/{entity_id:path}")
async def get_state(entity_id: str):
    """Get state of a specific entity."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{HA_URL}/api/states/{entity_id}", headers=_headers())
    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return resp.json()


class ServiceCall(BaseModel):
    entity_id: str


@router.post("/turn-on")
async def turn_on(service: ServiceCall):
    """Turn on a device."""
    err = _check_auth()
    if err:
        return err
    domain = service.entity_id.split(".")[0]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HA_URL}/api/services/{domain}/turn_on",
            headers=_headers(),
            json={"entity_id": service.entity_id},
        )
    return {"status": "on", "entity": service.entity_id, "message": f"{service.entity_id} turned on, sir."}


@router.post("/turn-off")
async def turn_off(service: ServiceCall):
    """Turn off a device."""
    err = _check_auth()
    if err:
        return err
    domain = service.entity_id.split(".")[0]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HA_URL}/api/services/{domain}/turn_off",
            headers=_headers(),
            json={"entity_id": service.entity_id},
        )
    return {"status": "off", "entity": service.entity_id, "message": f"{service.entity_id} turned off, sir."}


@router.post("/toggle")
async def toggle(service: ServiceCall):
    """Toggle a device."""
    err = _check_auth()
    if err:
        return err
    domain = service.entity_id.split(".")[0]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HA_URL}/api/services/{domain}/toggle",
            headers=_headers(),
            json={"entity_id": service.entity_id},
        )
    return {"status": "toggled", "entity": service.entity_id, "message": f"{service.entity_id} toggled, sir."}


class ThermostatSet(BaseModel):
    entity_id: str
    temperature: float


@router.post("/thermostat")
async def set_thermostat(data: ThermostatSet):
    """Set thermostat temperature."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HA_URL}/api/services/climate/set_temperature",
            headers=_headers(),
            json={"entity_id": data.entity_id, "temperature": data.temperature},
        )
    return {"status": "set", "temperature": data.temperature, "message": f"Thermostat set to {data.temperature}°, sir."}


class SceneActivate(BaseModel):
    entity_id: str


@router.post("/scene")
async def activate_scene(data: SceneActivate):
    """Activate a Home Assistant scene."""
    err = _check_auth()
    if err:
        return err
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HA_URL}/api/services/scene/turn_on",
            headers=_headers(),
            json={"entity_id": data.entity_id},
        )
    return {"status": "activated", "scene": data.entity_id, "message": "Scene activated, sir."}
