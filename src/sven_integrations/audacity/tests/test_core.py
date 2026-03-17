"""Tests for the Audacity harness: project model, core modules, and backend."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sven_integrations.audacity.backend import AudacityBackend, AudacityConnectionError
from sven_integrations.audacity.core import clips as clip_mod
from sven_integrations.audacity.core import effects as fx_mod
from sven_integrations.audacity.core import labels as label_mod
from sven_integrations.audacity.core import media as media_mod
from sven_integrations.audacity.core import selection as sel_mod
from sven_integrations.audacity.core import tracks as track_mod
from sven_integrations.audacity.core.clips import ClipInfo
from sven_integrations.audacity.core.export import build_export_command, export_mp3, export_wav
from sven_integrations.audacity.core.labels import LabelMark
from sven_integrations.audacity.core.media import MediaInfo, format_duration, format_file_size
from sven_integrations.audacity.project import AudioClip, AudioProject, AudioTrack

# ---------------------------------------------------------------------------
# AudioClip tests

class TestAudioClip:
    def test_roundtrip(self) -> None:
        clip = AudioClip(
            clip_id="c1",
            start_seconds=0.0,
            end_seconds=5.0,
            source_path="/audio/sample.wav",
        )
        restored = AudioClip.from_dict(clip.to_dict())
        assert restored.clip_id == "c1"
        assert restored.end_seconds == 5.0
        assert restored.source_path == "/audio/sample.wav"


# ---------------------------------------------------------------------------
# AudioTrack tests

class TestAudioTrack:
    def test_valid_kinds(self) -> None:
        for kind in ("mono", "stereo", "label", "time"):
            t = AudioTrack(track_id="t1", name="Test", kind=kind)
            assert t.kind == kind

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            AudioTrack(track_id="t1", name="Bad", kind="unknown")

    def test_pan_bounds(self) -> None:
        with pytest.raises(ValueError, match="Pan"):
            AudioTrack(track_id="t2", name="Loud", kind="mono", pan=2.0)

    def test_roundtrip(self) -> None:
        track = AudioTrack(
            track_id="t3",
            name="Vocals",
            kind="stereo",
            muted=True,
            pan=0.5,
            clips=[AudioClip("c1", 0.0, 3.0, "/tmp/a.wav")],
        )
        restored = AudioTrack.from_dict(track.to_dict())
        assert restored.name == "Vocals"
        assert restored.muted is True
        assert restored.pan == 0.5
        assert len(restored.clips) == 1


# ---------------------------------------------------------------------------
# AudioProject tests

class TestAudioProject:
    def _make_project(self) -> AudioProject:
        return AudioProject(name="TestProject", sample_rate=48000, channels=2, bit_depth=24)

    def test_add_and_find_track(self) -> None:
        proj = self._make_project()
        t = AudioTrack(track_id="t1", name="Lead Guitar", kind="mono")
        proj.add_track(t)
        found = proj.find_track("Lead Guitar")
        assert found is not None
        assert found.track_id == "t1"

    def test_find_missing_returns_none(self) -> None:
        proj = self._make_project()
        assert proj.find_track("Ghost") is None

    def test_remove_track(self) -> None:
        proj = self._make_project()
        proj.add_track(AudioTrack(track_id="t1", name="Drums", kind="stereo"))
        removed = proj.remove_track("t1")
        assert removed.name == "Drums"
        assert proj.total_tracks() == 0

    def test_remove_missing_raises(self) -> None:
        proj = self._make_project()
        with pytest.raises(KeyError):
            proj.remove_track("nonexistent")

    def test_total_tracks(self) -> None:
        proj = self._make_project()
        for i in range(3):
            proj.add_track(AudioTrack(track_id=f"t{i}", name=f"Track {i}", kind="mono"))
        assert proj.total_tracks() == 3

    def test_roundtrip_empty(self) -> None:
        proj = self._make_project()
        restored = AudioProject.from_dict(proj.to_dict())
        assert restored.name == "TestProject"
        assert restored.sample_rate == 48000
        assert restored.bit_depth == 24

    def test_roundtrip_with_tracks(self) -> None:
        proj = self._make_project()
        proj.add_track(AudioTrack(track_id="t1", name="Bass", kind="mono"))
        restored = AudioProject.from_dict(proj.to_dict())
        assert len(restored.tracks) == 1
        assert restored.tracks[0].name == "Bass"


# ---------------------------------------------------------------------------
# Backend mock tests

def _make_backend(reply: str = "BatchCommand finished: OK") -> AudacityBackend:
    backend = MagicMock(spec=AudacityBackend)
    backend.send_command.return_value = reply
    backend.is_connected.return_value = True
    return backend


class TestTrackCommands:
    def test_new_mono_track(self) -> None:
        b = _make_backend()
        track_mod.new_mono_track(b, "Lead")
        b.send_command.assert_any_call("NewMonoTrack")

    def test_new_stereo_track(self) -> None:
        b = _make_backend()
        track_mod.new_stereo_track(b, "Drums")
        b.send_command.assert_any_call("NewStereoTrack")

    def test_delete_track(self) -> None:
        b = _make_backend()
        track_mod.delete_track(b, 2)
        calls = [str(c) for c in b.send_command.call_args_list]
        assert any("RemoveTracks" in c for c in calls)

    def test_set_gain(self) -> None:
        b = _make_backend()
        track_mod.set_gain(b, 0, -6.0)
        calls = [str(c) for c in b.send_command.call_args_list]
        assert any("Gain=-6.0" in c for c in calls)

    def test_set_pan_valid(self) -> None:
        b = _make_backend()
        track_mod.set_pan(b, 0, 0.5)
        calls = [str(c) for c in b.send_command.call_args_list]
        assert any("Pan=0.5" in c for c in calls)

    def test_set_pan_invalid(self) -> None:
        b = _make_backend()
        with pytest.raises(ValueError, match="Pan"):
            track_mod.set_pan(b, 0, 2.0)


class TestSelectionCommands:
    def test_select_all(self) -> None:
        b = _make_backend()
        sel_mod.select_all(b)
        b.send_command.assert_called_once_with("SelectAll")

    def test_select_none(self) -> None:
        b = _make_backend()
        sel_mod.select_none(b)
        b.send_command.assert_called_once_with("SelectNone")

    def test_select_time(self) -> None:
        b = _make_backend()
        sel_mod.select_time(b, 1.0, 5.0)
        cmd = b.send_command.call_args[0][0]
        assert "Start=1.0" in cmd
        assert "End=5.0" in cmd

    def test_select_time_invalid(self) -> None:
        b = _make_backend()
        with pytest.raises(ValueError):
            sel_mod.select_time(b, 5.0, 1.0)

    def test_trim_to_selection(self) -> None:
        b = _make_backend()
        sel_mod.trim_to_selection(b)
        b.send_command.assert_called_once_with("Trim")


class TestEffectCommands:
    def test_apply_normalize(self) -> None:
        b = _make_backend()
        fx_mod.apply_normalize(b, -2.0)
        cmd = b.send_command.call_args[0][0]
        assert "PeakLevel=-2.0" in cmd

    def test_apply_amplify(self) -> None:
        b = _make_backend()
        fx_mod.apply_amplify(b, 6.0)
        cmd = b.send_command.call_args[0][0]
        assert "Amplify" in cmd

    def test_apply_fade_in(self) -> None:
        b = _make_backend()
        fx_mod.apply_fade_in(b)
        b.send_command.assert_called_once_with("FadeIn")

    def test_apply_fade_out(self) -> None:
        b = _make_backend()
        fx_mod.apply_fade_out(b)
        b.send_command.assert_called_once_with("FadeOut")

    def test_apply_eq(self) -> None:
        b = _make_backend()
        fx_mod.apply_eq(b, [(100.0, 3.0), (8000.0, -2.0)])
        cmd = b.send_command.call_args[0][0]
        assert "FilterCurveEQ" in cmd
        assert "f=100.0" in cmd

    def test_apply_compressor(self) -> None:
        b = _make_backend()
        fx_mod.apply_compressor(b, threshold=-18.0, ratio=3.0)
        cmd = b.send_command.call_args[0][0]
        assert "Threshold=-18.0" in cmd
        assert "Ratio=3.0" in cmd


class TestExportCommands:
    def test_build_export_command_wav(self) -> None:
        cmd = build_export_command("wav", "/out/audio.wav", SubFormat="PCM_16_bit")
        assert "Export2" in cmd
        assert "/out/audio.wav" in cmd
        assert "WAV" in cmd
        assert "PCM_16_bit" in cmd

    def test_build_export_command_mp3(self) -> None:
        cmd = build_export_command("mp3", "/out/song.mp3", VBRMode=2)
        assert "MP3" in cmd

    def test_export_wav_invalid_depth(self) -> None:
        b = _make_backend()
        with pytest.raises(ValueError, match="bit depth"):
            export_wav(b, "/tmp/out.wav", bit_depth=8)

    def test_export_mp3_sends_command(self) -> None:
        b = _make_backend()
        export_mp3(b, "/tmp/song.mp3", quality=2)
        b.send_command.assert_called_once()
        cmd = b.send_command.call_args[0][0]
        assert "MP3" in cmd

    def test_export_wav_sends_command(self) -> None:
        b = _make_backend()
        export_wav(b, "/tmp/out.wav", bit_depth=24)
        b.send_command.assert_called_once()
        cmd = b.send_command.call_args[0][0]
        assert "PCM_24_bit" in cmd


# ---------------------------------------------------------------------------
# Clips CRUD tests

def _make_project_with_track() -> AudioProject:
    proj = AudioProject(name="ClipTest", sample_rate=44100, channels=2, bit_depth=16)
    proj.add_track(AudioTrack(track_id="t1", name="Vocals", kind="mono"))
    return proj


class TestClips:
    def test_add_clip_appends_to_track(self) -> None:
        proj = _make_project_with_track()
        result = clip_mod.add_clip(
            proj, 0, "/audio/vocal.wav", name="Intro", start_seconds=0.0, end_seconds=4.0
        )
        assert result["action"] == "add_clip"
        assert len(proj.tracks[0].clips) == 1
        clip = proj.tracks[0].clips[0]
        assert getattr(clip, "name") == "Intro"
        assert getattr(clip, "start_seconds") == 0.0
        assert getattr(clip, "end_seconds") == 4.0

    def test_add_clip_default_name_from_path(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/guitar.wav", start_seconds=0.0, end_seconds=2.0)
        clip = proj.tracks[0].clips[0]
        assert getattr(clip, "name") == "guitar.wav"

    def test_add_clip_invalid_track_raises(self) -> None:
        proj = _make_project_with_track()
        with pytest.raises(IndexError):
            clip_mod.add_clip(proj, 99, "/audio/x.wav")

    def test_add_clip_volume_stored(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/x.wav", start_seconds=0.0, end_seconds=1.0, volume=0.5)
        assert getattr(proj.tracks[0].clips[0], "volume") == 0.5

    def test_remove_clip(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/a.wav", start_seconds=0.0, end_seconds=2.0)
        clip_mod.add_clip(proj, 0, "/audio/b.wav", start_seconds=3.0, end_seconds=5.0)
        result = clip_mod.remove_clip(proj, 0, 0)
        assert result["action"] == "remove_clip"
        assert len(proj.tracks[0].clips) == 1
        remaining = proj.tracks[0].clips[0]
        assert getattr(remaining, "source_path") == "/audio/b.wav"

    def test_remove_clip_invalid_index_raises(self) -> None:
        proj = _make_project_with_track()
        with pytest.raises(IndexError):
            clip_mod.remove_clip(proj, 0, 5)

    def test_trim_clip(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/x.wav", start_seconds=0.0, end_seconds=10.0)
        result = clip_mod.trim_clip(proj, 0, 0, trim_in=1.5, trim_out=0.5)
        assert result["trim_in"] == 1.5
        assert result["trim_out"] == 0.5
        clip = proj.tracks[0].clips[0]
        assert getattr(clip, "trim_in") == 1.5
        assert getattr(clip, "trim_out") == 0.5

    def test_split_clip(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/long.wav", start_seconds=0.0, end_seconds=10.0)
        result = clip_mod.split_clip(proj, 0, 0, split_at_seconds=5.0)
        assert result["action"] == "split_clip"
        assert len(proj.tracks[0].clips) == 2
        first = proj.tracks[0].clips[0]
        second = proj.tracks[0].clips[1]
        assert getattr(first, "end_seconds") == 5.0
        assert getattr(second, "start_seconds") == 5.0
        assert getattr(second, "end_seconds") == 10.0

    def test_split_clip_out_of_bounds_raises(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/x.wav", start_seconds=0.0, end_seconds=5.0)
        with pytest.raises(ValueError):
            clip_mod.split_clip(proj, 0, 0, split_at_seconds=6.0)

    def test_move_clip(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/x.wav", start_seconds=2.0, end_seconds=7.0)
        result = clip_mod.move_clip(proj, 0, 0, new_start_seconds=10.0)
        assert result["new_start_seconds"] == 10.0
        assert result["end_seconds"] == 15.0
        clip = proj.tracks[0].clips[0]
        assert getattr(clip, "start_seconds") == 10.0
        assert getattr(clip, "end_seconds") == 15.0

    def test_list_clips(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/audio/a.wav", start_seconds=0.0, end_seconds=3.0)
        clip_mod.add_clip(proj, 0, "/audio/b.wav", start_seconds=4.0, end_seconds=6.0)
        result = clip_mod.list_clips(proj, 0)
        assert result["action"] == "list_clips"
        assert result["count"] == 2
        assert result["clips"][0]["index"] == 0
        assert result["clips"][1]["index"] == 1

    def test_clip_info_roundtrip(self) -> None:
        ci = ClipInfo(
            clip_id="abc",
            name="Test",
            source_path="/x.wav",
            start_seconds=1.0,
            end_seconds=3.0,
            trim_in=0.2,
            trim_out=0.1,
            volume=0.8,
        )
        restored = ClipInfo.from_dict(ci.to_dict())
        assert restored.clip_id == "abc"
        assert restored.trim_in == 0.2
        assert restored.volume == 0.8

    def test_probe_audio_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            clip_mod.probe_audio("/nonexistent/path/file.wav")

    def test_probe_audio_non_wav_returns_metadata(self, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "test.mp3"
        p.write_bytes(b"\xff\xfb" * 100)
        result = clip_mod.probe_audio(str(p))
        assert result["format"] == "mp3"
        assert result["sample_rate"] is None
        assert result["file_size_bytes"] == 200


# ---------------------------------------------------------------------------
# Labels tests

def _make_empty_project() -> AudioProject:
    return AudioProject(name="LabelTest")


class TestLabels:
    def test_add_point_label(self) -> None:
        proj = _make_empty_project()
        result = label_mod.add_label(proj, start=1.5, text="Verse 1")
        assert result["action"] == "add_label"
        assert result["label"]["type"] == "point"
        assert result["label"]["text"] == "Verse 1"
        assert len(proj.data["labels"]) == 1

    def test_add_region_label(self) -> None:
        proj = _make_empty_project()
        result = label_mod.add_label(proj, start=2.0, end=5.0, text="Chorus")
        assert result["label"]["type"] == "region"
        assert result["label"]["end_seconds"] == 5.0

    def test_remove_label(self) -> None:
        proj = _make_empty_project()
        result = label_mod.add_label(proj, start=1.0, text="Marker")
        lid = result["label"]["label_id"]
        removed = label_mod.remove_label(proj, lid)
        assert removed["action"] == "remove_label"
        assert removed["removed"]["label_id"] == lid
        assert len(proj.data["labels"]) == 0

    def test_remove_missing_label_raises(self) -> None:
        proj = _make_empty_project()
        with pytest.raises(KeyError):
            label_mod.remove_label(proj, "nonexistent-id")

    def test_list_labels_sorted_by_start(self) -> None:
        proj = _make_empty_project()
        label_mod.add_label(proj, start=10.0, text="Late")
        label_mod.add_label(proj, start=2.0, text="Early")
        label_mod.add_label(proj, start=5.5, text="Middle")
        result = label_mod.list_labels(proj)
        assert result["count"] == 3
        starts = [lbl["start_seconds"] for lbl in result["labels"]]
        assert starts == sorted(starts)
        assert result["labels"][0]["text"] == "Early"

    def test_list_labels_empty(self) -> None:
        proj = _make_empty_project()
        result = label_mod.list_labels(proj)
        assert result["count"] == 0
        assert result["labels"] == []

    def test_build_label_track_commands_empty(self) -> None:
        proj = _make_empty_project()
        cmds = label_mod.build_label_track_commands(proj)
        assert cmds == []

    def test_build_label_track_commands_with_labels(self) -> None:
        proj = _make_empty_project()
        label_mod.add_label(proj, start=0.5, text="Intro")
        label_mod.add_label(proj, start=3.0, end=6.0, text="Bridge")
        cmds = label_mod.build_label_track_commands(proj)
        assert cmds[0] == "NewLabelTrack"
        assert len(cmds) == 3
        assert any("Intro" in c for c in cmds)
        assert any("Bridge" in c for c in cmds)

    def test_label_mark_is_region(self) -> None:
        point = LabelMark(label_id="x", start_seconds=1.0, end_seconds=None, text="P")
        region = LabelMark(label_id="y", start_seconds=1.0, end_seconds=3.0, text="R")
        assert not point.is_region
        assert region.is_region


# ---------------------------------------------------------------------------
# Media tests

class TestMedia:
    def test_probe_media_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            media_mod.probe_media("/no/such/file.wav")

    def test_probe_media_non_wav_fallback(self, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "audio.flac"
        p.write_bytes(b"fLaC" + b"\x00" * 64)
        info = media_mod.probe_media(str(p))
        assert isinstance(info, MediaInfo)
        assert info.format_name == "flac"
        assert info.sample_rate is None
        assert info.duration_seconds is None
        assert info.file_size_bytes > 0

    def test_probe_media_wav(self, tmp_path: object) -> None:
        import pathlib
        import wave as wv
        p = pathlib.Path(str(tmp_path)) / "test.wav"
        with wv.open(str(p), "w") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b"\x00" * 44100 * 2 * 2)
        info = media_mod.probe_media(str(p))
        assert info.format_name == "wav"
        assert info.sample_rate == 44100
        assert info.channels == 2
        assert info.bit_depth == 16
        assert abs(info.duration_seconds - 1.0) < 0.01

    def test_check_project_media_all_missing(self) -> None:
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, "/nonexistent/audio.wav", start_seconds=0.0, end_seconds=1.0)
        result = media_mod.check_project_media(proj)
        assert result["ok"] is False
        assert "/nonexistent/audio.wav" in result["missing"]
        assert result["found"] == []

    def test_check_project_media_existing(self, tmp_path: object) -> None:
        import pathlib
        p = pathlib.Path(str(tmp_path)) / "real.wav"
        p.write_bytes(b"\x00" * 100)
        proj = _make_project_with_track()
        clip_mod.add_clip(proj, 0, str(p), start_seconds=0.0, end_seconds=1.0)
        result = media_mod.check_project_media(proj)
        assert result["ok"] is True
        assert str(p) in result["found"]
        assert result["missing"] == []

    def test_check_project_media_empty_project(self) -> None:
        proj = AudioProject(name="Empty")
        result = media_mod.check_project_media(proj)
        assert result["ok"] is True
        assert result["missing"] == []
        assert result["found"] == []

    def test_format_duration_zero(self) -> None:
        assert format_duration(0.0) == "00:00:00.000"

    def test_format_duration_seconds(self) -> None:
        assert format_duration(65.5) == "00:01:05.500"

    def test_format_duration_hours(self) -> None:
        assert format_duration(3661.001) == "01:01:01.001"

    def test_format_file_size_bytes(self) -> None:
        assert format_file_size(512) == "512 B"

    def test_format_file_size_kb(self) -> None:
        result = format_file_size(2048)
        assert "KB" in result

    def test_format_file_size_mb(self) -> None:
        result = format_file_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_estimate_project_duration(self) -> None:
        proj = _make_project_with_track()
        proj.add_track(AudioTrack(track_id="t2", name="Bass", kind="mono"))
        clip_mod.add_clip(proj, 0, "/a.wav", start_seconds=0.0, end_seconds=10.0)
        clip_mod.add_clip(proj, 1, "/b.wav", start_seconds=5.0, end_seconds=18.5)
        dur = media_mod.estimate_project_duration(proj)
        assert dur == 18.5

    def test_estimate_project_duration_empty(self) -> None:
        proj = AudioProject(name="Empty")
        assert media_mod.estimate_project_duration(proj) == 0.0


# ---------------------------------------------------------------------------
# Backend connection tests

class TestAudacityBackend:
    def test_not_connected_initially(self) -> None:
        b = AudacityBackend()
        assert not b.is_connected()

    def test_send_command_without_connect_raises(self) -> None:
        b = AudacityBackend()
        with pytest.raises(AudacityConnectionError, match="connect"):
            b.send_command("SelectAll")

    def test_connect_raises_when_pipe_missing(self, tmp_path: object) -> None:
        b = AudacityBackend()
        with pytest.raises(AudacityConnectionError):
            b.connect()
