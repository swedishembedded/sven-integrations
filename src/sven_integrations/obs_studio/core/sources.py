"""Source management via OBS WebSocket calls."""

from __future__ import annotations

from typing import Any

from ..backend import ObsBackend


def list_sources(backend: ObsBackend, scene_name: str) -> list[dict[str, Any]]:
    """Return all sources in *scene_name* as a list of dicts."""
    data = backend.call("GetSceneItemList", {"sceneName": scene_name})
    return data.get("sceneItems", [])


def add_source(
    backend: ObsBackend,
    scene: str,
    name: str,
    kind: str,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new input source of *kind* named *name* and add it to *scene*.

    Returns the scene item data dict from OBS.
    """
    backend.call(
        "CreateInput",
        {
            "sceneName": scene,
            "inputName": name,
            "inputKind": kind,
            "inputSettings": settings or {},
        },
    )
    items = list_sources(backend, scene)
    for item in items:
        if item.get("sourceName") == name:
            return item
    return {"sourceName": name, "inputKind": kind}


def remove_source(backend: ObsBackend, scene: str, name: str) -> None:
    """Remove the scene item *name* from *scene*."""
    items = backend.call("GetSceneItemList", {"sceneName": scene})
    for item in items.get("sceneItems", []):
        if item.get("sourceName") == name:
            backend.call(
                "RemoveSceneItem",
                {"sceneName": scene, "sceneItemId": item["sceneItemId"]},
            )
            return
    from ..backend import ObsRequestError
    raise ObsRequestError(f"Source {name!r} not found in scene {scene!r}")


def set_source_volume(backend: ObsBackend, name: str, volume_db: float) -> None:
    """Set the volume of input *name* to *volume_db* decibels (mul)."""
    backend.call("SetInputVolume", {"inputName": name, "inputVolumeDb": volume_db})


def mute_source(backend: ObsBackend, name: str) -> None:
    """Mute the input source *name*."""
    backend.call("SetInputMute", {"inputName": name, "inputMuted": True})


def unmute_source(backend: ObsBackend, name: str) -> None:
    """Unmute the input source *name*."""
    backend.call("SetInputMute", {"inputName": name, "inputMuted": False})


def set_source_visible(
    backend: ObsBackend, scene: str, name: str, visible: bool
) -> None:
    """Show or hide source *name* within *scene*."""
    items = backend.call("GetSceneItemList", {"sceneName": scene})
    for item in items.get("sceneItems", []):
        if item.get("sourceName") == name:
            backend.call(
                "SetSceneItemEnabled",
                {
                    "sceneName": scene,
                    "sceneItemId": item["sceneItemId"],
                    "sceneItemEnabled": visible,
                },
            )
            return
    from ..backend import ObsRequestError
    raise ObsRequestError(f"Source {name!r} not found in scene {scene!r}")


def refresh_browser_source(backend: ObsBackend, name: str) -> None:
    """Trigger a page reload on the browser source *name*."""
    backend.call("PressInputPropertiesButton", {"inputName": name, "propertyName": "refreshnocache"})


def take_source_screenshot(backend: ObsBackend, name: str, path: str) -> dict[str, Any]:
    """Save a screenshot of source *name* to *path*.

    Returns the OBS response dict which includes ``imageFile``.
    """
    return backend.call(
        "SaveSourceScreenshot",
        {"sourceName": name, "imageFormat": "png", "imageFilePath": path},
    )
