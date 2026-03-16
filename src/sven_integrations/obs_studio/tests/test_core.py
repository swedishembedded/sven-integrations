"""Tests for the OBS Studio harness: project model, core modules, and backend."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from sven_integrations.obs_studio.project import ObsSetup, ObsScene, ObsSource
from sven_integrations.obs_studio.backend import ObsBackend, ObsConnectionError, ObsRequestError
from sven_integrations.obs_studio.core import scenes as scene_mod
from sven_integrations.obs_studio.core import recording as rec_mod
from sven_integrations.obs_studio.core import sources as src_mod
from sven_integrations.obs_studio.core import audio as audio_mod
from sven_integrations.obs_studio.core import filters as filter_mod
from sven_integrations.obs_studio.core import output as output_mod
from sven_integrations.obs_studio.core import transitions as trans_mod


# ---------------------------------------------------------------------------
# ObsSource tests

class TestObsSource:
    def test_valid_kinds(self) -> None:
        for kind in ("video_capture", "audio_capture", "image", "browser", "display_capture", "text"):
            src = ObsSource(name="test", kind=kind)
            assert src.kind == kind

    def test_invalid_kind(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            ObsSource(name="bad", kind="laser_pointer")

    def test_roundtrip(self) -> None:
        src = ObsSource(
            name="webcam",
            kind="video_capture",
            settings={"device": "/dev/video0"},
            volume=0.8,
            muted=True,
        )
        restored = ObsSource.from_dict(src.to_dict())
        assert restored.name == "webcam"
        assert restored.kind == "video_capture"
        assert restored.settings["device"] == "/dev/video0"
        assert restored.muted is True
        assert restored.volume == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# ObsScene tests

class TestObsScene:
    def test_add_and_find_source(self) -> None:
        scene = ObsScene(name="Main")
        scene.add_source(ObsSource(name="mic", kind="audio_capture"))
        found = scene.find_source("mic")
        assert found is not None
        assert found.kind == "audio_capture"

    def test_remove_source(self) -> None:
        scene = ObsScene(name="Main")
        scene.add_source(ObsSource(name="cam", kind="video_capture"))
        removed = scene.remove_source("cam")
        assert removed.name == "cam"
        assert len(scene.sources) == 0

    def test_remove_missing_raises(self) -> None:
        scene = ObsScene(name="Main")
        with pytest.raises(KeyError):
            scene.remove_source("ghost")

    def test_roundtrip(self) -> None:
        scene = ObsScene(name="Gaming")
        scene.add_source(ObsSource(name="game_cap", kind="display_capture"))
        restored = ObsScene.from_dict(scene.to_dict())
        assert restored.name == "Gaming"
        assert len(restored.sources) == 1
        assert restored.sources[0].name == "game_cap"


# ---------------------------------------------------------------------------
# ObsSetup tests

class TestObsSetup:
    def _make_setup(self) -> ObsSetup:
        return ObsSetup(
            profile_name="Streaming",
            scene_collection_name="MyCollection",
        )

    def test_add_and_find_scene(self) -> None:
        setup = self._make_setup()
        setup.add_scene(ObsScene(name="Intro"))
        found = setup.find_scene("Intro")
        assert found is not None

    def test_remove_scene(self) -> None:
        setup = self._make_setup()
        setup.add_scene(ObsScene(name="BRB"))
        removed = setup.remove_scene("BRB")
        assert removed.name == "BRB"
        assert len(setup.scenes) == 0

    def test_remove_missing_scene_raises(self) -> None:
        setup = self._make_setup()
        with pytest.raises(KeyError):
            setup.remove_scene("Nonexistent")

    def test_add_source_to_scene(self) -> None:
        setup = self._make_setup()
        setup.add_scene(ObsScene(name="Live"))
        setup.add_source("Live", ObsSource(name="cam", kind="video_capture"))
        scene = setup.find_scene("Live")
        assert scene is not None
        assert scene.find_source("cam") is not None

    def test_add_source_missing_scene_raises(self) -> None:
        setup = self._make_setup()
        with pytest.raises(KeyError):
            setup.add_source("Ghost", ObsSource(name="cam", kind="video_capture"))

    def test_roundtrip_empty(self) -> None:
        setup = self._make_setup()
        restored = ObsSetup.from_dict(setup.to_dict())
        assert restored.profile_name == "Streaming"
        assert restored.scene_collection_name == "MyCollection"
        assert restored.scenes == []

    def test_roundtrip_with_scenes(self) -> None:
        setup = self._make_setup()
        scene = ObsScene(name="Desktop")
        scene.add_source(ObsSource(name="screen", kind="display_capture"))
        setup.add_scene(scene)
        restored = ObsSetup.from_dict(setup.to_dict())
        assert len(restored.scenes) == 1
        assert restored.scenes[0].name == "Desktop"
        assert len(restored.scenes[0].sources) == 1


# ---------------------------------------------------------------------------
# Backend mock helpers

def _make_backend(response: dict | None = None) -> ObsBackend:
    b = MagicMock(spec=ObsBackend)
    b.is_connected.return_value = True
    b.call.return_value = response or {}
    return b


# ---------------------------------------------------------------------------
# Scene command tests

class TestSceneCommands:
    def test_list_scenes(self) -> None:
        b = _make_backend({"scenes": [{"sceneName": "Main"}, {"sceneName": "BRB"}]})
        names = scene_mod.list_scenes(b)
        assert names == ["Main", "BRB"]
        b.call.assert_called_once_with("GetSceneList")

    def test_switch_scene(self) -> None:
        b = _make_backend()
        scene_mod.switch_scene(b, "Gaming")
        b.call.assert_called_once_with("SetCurrentProgramScene", {"sceneName": "Gaming"})

    def test_create_scene(self) -> None:
        b = _make_backend()
        scene_mod.create_scene(b, "New Scene")
        b.call.assert_called_once_with("CreateScene", {"sceneName": "New Scene"})

    def test_remove_scene(self) -> None:
        b = _make_backend()
        scene_mod.remove_scene(b, "Old Scene")
        b.call.assert_called_once_with("RemoveScene", {"sceneName": "Old Scene"})

    def test_get_current_scene(self) -> None:
        b = _make_backend({"sceneName": "Live"})
        name = scene_mod.get_current_scene(b)
        assert name == "Live"

    def test_duplicate_scene(self) -> None:
        b = _make_backend()
        scene_mod.duplicate_scene(b, "Main", "Main Copy")
        b.call.assert_called_once_with(
            "DuplicateScene",
            {"sceneName": "Main", "duplicateSceneName": "Main Copy"},
        )


# ---------------------------------------------------------------------------
# Recording command tests

class TestRecordingCommands:
    def test_start_recording(self) -> None:
        b = _make_backend()
        rec_mod.start_recording(b)
        b.call.assert_called_once_with("StartRecord")

    def test_stop_recording(self) -> None:
        b = _make_backend({"outputPath": "/recordings/output.mkv"})
        result = rec_mod.stop_recording(b)
        assert result.get("outputPath") == "/recordings/output.mkv"

    def test_toggle_recording(self) -> None:
        b = _make_backend()
        rec_mod.toggle_recording(b)
        b.call.assert_called_once_with("ToggleRecord")

    def test_start_streaming(self) -> None:
        b = _make_backend()
        rec_mod.start_streaming(b)
        b.call.assert_called_once_with("StartStream")

    def test_stop_streaming(self) -> None:
        b = _make_backend()
        rec_mod.stop_streaming(b)
        b.call.assert_called_once_with("StopStream")

    def test_get_recording_status(self) -> None:
        b = _make_backend({"outputActive": True, "outputTimecode": "00:01:23.456"})
        status = rec_mod.get_recording_status(b)
        assert status["outputActive"] is True

    def test_set_recording_path(self) -> None:
        b = _make_backend()
        rec_mod.set_recording_path(b, "/data/recordings")
        b.call.assert_called_once_with(
            "SetRecordDirectory", {"recordDirectory": "/data/recordings"}
        )


# ---------------------------------------------------------------------------
# Sources command tests

class TestSourceCommands:
    def test_list_sources(self) -> None:
        items = [
            {"sourceName": "webcam", "inputKind": "v4l2_input"},
            {"sourceName": "mic", "inputKind": "pulse_input_capture"},
        ]
        b = _make_backend({"sceneItems": items})
        result = src_mod.list_sources(b, "Main")
        assert len(result) == 2
        b.call.assert_called_once_with("GetSceneItemList", {"sceneName": "Main"})

    def test_mute_source(self) -> None:
        b = _make_backend()
        src_mod.mute_source(b, "mic")
        b.call.assert_called_once_with("SetInputMute", {"inputName": "mic", "inputMuted": True})

    def test_unmute_source(self) -> None:
        b = _make_backend()
        src_mod.unmute_source(b, "mic")
        b.call.assert_called_once_with("SetInputMute", {"inputName": "mic", "inputMuted": False})

    def test_set_source_volume(self) -> None:
        b = _make_backend()
        src_mod.set_source_volume(b, "game_audio", -6.0)
        b.call.assert_called_once_with(
            "SetInputVolume", {"inputName": "game_audio", "inputVolumeDb": -6.0}
        )

    def test_refresh_browser_source(self) -> None:
        b = _make_backend()
        src_mod.refresh_browser_source(b, "overlay")
        b.call.assert_called_once_with(
            "PressInputPropertiesButton",
            {"inputName": "overlay", "propertyName": "refreshnocache"},
        )

    def test_take_source_screenshot(self) -> None:
        b = _make_backend({"imageFile": "/tmp/screenshot.png"})
        result = src_mod.take_source_screenshot(b, "webcam", "/tmp/screenshot.png")
        assert result.get("imageFile") == "/tmp/screenshot.png"


# ---------------------------------------------------------------------------
# Backend unit tests

class TestObsBackend:
    def test_not_connected_initially(self) -> None:
        b = ObsBackend()
        assert not b.is_connected()

    def test_call_without_connect_raises(self) -> None:
        b = ObsBackend()
        with pytest.raises(ObsConnectionError, match="connect"):
            b.call("GetVersion")

    def test_compute_auth(self) -> None:
        auth = ObsBackend._compute_auth("password", "challenge", "salt")
        assert isinstance(auth, str)
        assert len(auth) > 0


# ---------------------------------------------------------------------------
# AudioSource tests


def _make_obs_setup() -> ObsSetup:
    return ObsSetup(profile_name="Test", scene_collection_name="TestCollection")


class TestAudioSource:
    def test_add_audio_source(self) -> None:
        setup = _make_obs_setup()
        result = audio_mod.add_audio_source(setup, "Mic", audio_type="input")
        assert result["name"] == "Mic"
        assert result["audio_type"] == "input"
        assert "source_id" in result

    def test_add_two_sources(self) -> None:
        setup = _make_obs_setup()
        audio_mod.add_audio_source(setup, "Mic", audio_type="input")
        audio_mod.add_audio_source(setup, "Desktop", audio_type="output")
        listing = audio_mod.list_audio(setup)
        assert listing["count"] == 2

    def test_list_audio_empty(self) -> None:
        setup = _make_obs_setup()
        listing = audio_mod.list_audio(setup)
        assert listing["count"] == 0
        assert listing["audio_sources"] == []

    def test_mute_unmute(self) -> None:
        setup = _make_obs_setup()
        audio_mod.add_audio_source(setup, "Mic")
        audio_mod.mute_source(setup, 0)
        assert setup.data["audio_sources"][0]["muted"] is True
        audio_mod.unmute_source(setup, 0)
        assert setup.data["audio_sources"][0]["muted"] is False

    def test_set_volume(self) -> None:
        setup = _make_obs_setup()
        audio_mod.add_audio_source(setup, "Mic")
        audio_mod.set_volume(setup, 0, 1.5)
        assert setup.data["audio_sources"][0]["volume"] == pytest.approx(1.5)

    def test_set_volume_out_of_range(self) -> None:
        setup = _make_obs_setup()
        audio_mod.add_audio_source(setup, "Mic")
        with pytest.raises(ValueError):
            audio_mod.set_volume(setup, 0, 5.0)

    def test_remove_audio_source(self) -> None:
        setup = _make_obs_setup()
        audio_mod.add_audio_source(setup, "Mic")
        removed = audio_mod.remove_audio_source(setup, 0)
        assert removed["name"] == "Mic"
        assert audio_mod.list_audio(setup)["count"] == 0

    def test_build_audio_requests(self) -> None:
        setup = _make_obs_setup()
        audio_mod.add_audio_source(setup, "Mic")
        requests = audio_mod.build_audio_requests(setup)
        types = [r["requestType"] for r in requests]
        assert "SetInputVolume" in types
        assert "SetInputMute" in types


# ---------------------------------------------------------------------------
# Filter tests


class TestFilterRegistry:
    def test_registry_not_empty(self) -> None:
        assert len(filter_mod.FILTER_REGISTRY) > 0

    def test_known_filters_present(self) -> None:
        for name in ("color_correction", "chroma_key", "gain", "compressor", "noise_gate"):
            assert name in filter_mod.FILTER_REGISTRY

    def test_list_available_all(self) -> None:
        items = filter_mod.list_available_filters()
        assert len(items) >= 8

    def test_list_available_audio_category(self) -> None:
        audio_filters = filter_mod.list_available_filters(category="audio")
        assert all(f["category"] == "audio" for f in audio_filters)

    def test_add_filter(self) -> None:
        setup = _make_obs_setup()
        result = filter_mod.add_filter(setup, "gain", "Mic", params={"db": 3.0})
        assert result["filter_type"] == "gain"
        assert result["source_name"] == "Mic"

    def test_add_invalid_filter_type(self) -> None:
        setup = _make_obs_setup()
        with pytest.raises(ValueError):
            filter_mod.add_filter(setup, "laser_gun", "Mic")

    def test_list_filters(self) -> None:
        setup = _make_obs_setup()
        filter_mod.add_filter(setup, "gain", "Mic", params={"db": 3.0})
        info = filter_mod.list_filters(setup, "Mic")
        assert info["count"] == 1

    def test_validate_filter_params_valid(self) -> None:
        result = filter_mod.validate_filter_params("gain", {"db": 5.0})
        assert result["valid"] is True

    def test_validate_filter_params_out_of_range(self) -> None:
        result = filter_mod.validate_filter_params("gain", {"db": 100.0})
        assert result["valid"] is False

    def test_remove_filter(self) -> None:
        setup = _make_obs_setup()
        filter_mod.add_filter(setup, "gain", "Mic", params={"db": 3.0})
        removed = filter_mod.remove_filter(setup, "Mic", 0)
        assert removed["filter_type"] == "gain"


# ---------------------------------------------------------------------------
# Output preset tests


class TestOutputPresets:
    def test_list_presets(self) -> None:
        presets = output_mod.list_presets()
        assert len(presets) >= 6
        names = [p["name"] for p in presets]
        assert "streaming_1080p" in names
        assert "recording_4k" in names

    def test_set_streaming(self) -> None:
        setup = _make_obs_setup()
        result = output_mod.set_streaming(setup, "twitch", "rtmp://live.twitch.tv/app", "abc123")
        assert result["service"] == "twitch"
        assert result["stream_key"] == "abc123"

    def test_set_recording(self) -> None:
        setup = _make_obs_setup()
        result = output_mod.set_recording(setup, "/recordings", "mkv", "high")
        assert result["output_path"] == "/recordings"
        assert result["output_format"] == "mkv"

    def test_get_output_info(self) -> None:
        setup = _make_obs_setup()
        output_mod.set_streaming(setup, "custom", "rtmp://server", "key")
        info = output_mod.get_output_info(setup)
        assert "streaming" in info


# ---------------------------------------------------------------------------
# Transition tests


class TestObsTransitions:
    def test_add_transition(self) -> None:
        setup = _make_obs_setup()
        result = trans_mod.add_transition(setup, "fade", name="My Fade", duration_ms=500)
        assert result["transition_type"] == "fade"
        assert result["duration_ms"] == 500
        assert result["active"] is True  # first transition is active

    def test_add_invalid_type(self) -> None:
        setup = _make_obs_setup()
        with pytest.raises(ValueError):
            trans_mod.add_transition(setup, "sparkle")

    def test_list_transitions(self) -> None:
        setup = _make_obs_setup()
        trans_mod.add_transition(setup, "cut")
        trans_mod.add_transition(setup, "fade")
        info = trans_mod.list_transitions(setup)
        assert info["count"] == 2

    def test_set_active_transition(self) -> None:
        setup = _make_obs_setup()
        trans_mod.add_transition(setup, "cut")
        trans_mod.add_transition(setup, "fade")
        trans_mod.set_active_transition(setup, 1)
        transitions = setup.data["transitions"]
        assert transitions[0]["active"] is False
        assert transitions[1]["active"] is True

    def test_build_transition_requests(self) -> None:
        setup = _make_obs_setup()
        trans_mod.add_transition(setup, "fade", name="Main Fade")
        requests = trans_mod.build_transition_requests(setup)
        types = [r["requestType"] for r in requests]
        assert "CreateSceneTransition" in types
