"""OBS Studio setup model — dataclass representation of an OBS configuration."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ObsSource:
    """A single source within an OBS scene."""

    name: str
    kind: str  # video_capture | audio_capture | image | browser | display_capture | text
    settings: dict[str, Any] = field(default_factory=dict)
    volume: float = 1.0
    muted: bool = False
    visible: bool = True

    _VALID_KINDS = frozenset({
        "video_capture", "audio_capture", "image",
        "browser", "display_capture", "text",
    })

    def __post_init__(self) -> None:
        if self.kind not in self._VALID_KINDS:
            raise ValueError(
                f"Source kind must be one of {self._VALID_KINDS}, got {self.kind!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "settings": self.settings,
            "volume": self.volume,
            "muted": self.muted,
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObsSource":
        return cls(
            name=data["name"],
            kind=data["kind"],
            settings=data.get("settings", {}),
            volume=float(data.get("volume", 1.0)),
            muted=bool(data.get("muted", False)),
            visible=bool(data.get("visible", True)),
        )


@dataclass
class ObsScene:
    """A scene containing one or more sources."""

    name: str
    sources: list[ObsSource] = field(default_factory=list)

    def add_source(self, source: ObsSource) -> None:
        self.sources.append(source)

    def remove_source(self, name: str) -> ObsSource:
        for i, s in enumerate(self.sources):
            if s.name == name:
                return self.sources.pop(i)
        raise KeyError(f"No source named {name!r}")

    def find_source(self, name: str) -> ObsSource | None:
        for s in self.sources:
            if s.name == name:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sources": [s.to_dict() for s in self.sources],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObsScene":
        sources = [ObsSource.from_dict(s) for s in data.get("sources", [])]
        return cls(name=data["name"], sources=sources)


@dataclass
class ObsSetup:
    """Top-level model for an OBS Studio configuration."""

    profile_name: str
    scene_collection_name: str
    scenes: list[ObsScene] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def add_scene(self, scene: ObsScene) -> None:
        self.scenes.append(scene)

    def remove_scene(self, name: str) -> ObsScene:
        for i, s in enumerate(self.scenes):
            if s.name == name:
                return self.scenes.pop(i)
        raise KeyError(f"No scene named {name!r}")

    def find_scene(self, name: str) -> ObsScene | None:
        for s in self.scenes:
            if s.name == name:
                return s
        return None

    def add_source(self, scene_name: str, source: ObsSource) -> None:
        scene = self.find_scene(scene_name)
        if scene is None:
            raise KeyError(f"No scene named {scene_name!r}")
        scene.add_source(source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "scene_collection_name": self.scene_collection_name,
            "scenes": [s.to_dict() for s in self.scenes],
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObsSetup":
        scenes = [ObsScene.from_dict(s) for s in data.get("scenes", [])]
        return cls(
            profile_name=data["profile_name"],
            scene_collection_name=data["scene_collection_name"],
            scenes=scenes,
            data=dict(data.get("data", {})),
        )
