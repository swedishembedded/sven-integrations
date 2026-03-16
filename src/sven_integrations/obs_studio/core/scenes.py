"""Scene management via OBS WebSocket calls."""

from __future__ import annotations

from ..backend import ObsBackend


def list_scenes(backend: ObsBackend) -> list[str]:
    """Return the names of all scenes in the current scene collection."""
    data = backend.call("GetSceneList")
    return [s["sceneName"] for s in data.get("scenes", [])]


def switch_scene(backend: ObsBackend, name: str) -> None:
    """Switch to the scene named *name*."""
    backend.call("SetCurrentProgramScene", {"sceneName": name})


def create_scene(backend: ObsBackend, name: str) -> None:
    """Create a new scene named *name*."""
    backend.call("CreateScene", {"sceneName": name})


def remove_scene(backend: ObsBackend, name: str) -> None:
    """Remove the scene named *name*."""
    backend.call("RemoveScene", {"sceneName": name})


def get_current_scene(backend: ObsBackend) -> str:
    """Return the name of the currently active program scene."""
    data = backend.call("GetCurrentProgramScene")
    return data.get("sceneName", "")


def duplicate_scene(backend: ObsBackend, src_name: str, dest_name: str) -> None:
    """Duplicate *src_name* into a new scene called *dest_name*."""
    backend.call("DuplicateScene", {"sceneName": src_name, "duplicateSceneName": dest_name})


def set_scene_item_transform(
    backend: ObsBackend,
    scene: str,
    source: str,
    x: float,
    y: float,
    width: float,
    height: float,
    rotation: float = 0.0,
) -> None:
    """Apply a positional transform to *source* within *scene*."""
    items = backend.call("GetSceneItemList", {"sceneName": scene})
    item_id: int | None = None
    for item in items.get("sceneItems", []):
        if item.get("sourceName") == source:
            item_id = item.get("sceneItemId")
            break
    if item_id is None:
        from ..backend import ObsRequestError
        raise ObsRequestError(f"Source {source!r} not found in scene {scene!r}")

    backend.call(
        "SetSceneItemTransform",
        {
            "sceneName": scene,
            "sceneItemId": item_id,
            "sceneItemTransform": {
                "positionX": x,
                "positionY": y,
                "boundsWidth": width,
                "boundsHeight": height,
                "rotation": rotation,
            },
        },
    )
