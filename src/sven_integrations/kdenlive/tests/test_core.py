"""pytest — Kdenlive harness core tests."""

from __future__ import annotations

import pytest

from sven_integrations.kdenlive.core import effects as eff_mod
from sven_integrations.kdenlive.core import render as render_mod
from sven_integrations.kdenlive.core import timeline as tl_mod
from sven_integrations.kdenlive.core import bin as bin_mod
from sven_integrations.kdenlive.core import guides as guide_mod
from sven_integrations.kdenlive.core import transitions as kd_trans_mod
from sven_integrations.kdenlive.project import (
    KdenliveProject,
    TimelineClip,
    TimelineTrack,
)

# ---------------------------------------------------------------------------
# KdenliveProject model


def make_project() -> KdenliveProject:
    proj = KdenliveProject(profile_name="hdv_1080_25p", fps_num=25, fps_den=1, width=1920, height=1080)
    return proj


def test_project_defaults() -> None:
    proj = make_project()
    assert proj.width == 1920
    assert proj.height == 1080
    assert proj.fps_num == 25
    assert proj.tracks == []
    assert proj.duration_seconds == 0.0


def test_project_add_and_find_track() -> None:
    proj = make_project()
    track = TimelineTrack(track_id="v1", name="Main Video", kind="video")
    proj.add_track(track)
    assert len(proj.tracks) == 1
    found = proj.find_track("Main Video")
    assert found is not None
    assert found.track_id == "v1"


def test_project_remove_track() -> None:
    proj = make_project()
    proj.add_track(TimelineTrack(track_id="v1", name="V1", kind="video"))
    proj.add_track(TimelineTrack(track_id="a1", name="A1", kind="audio"))
    removed = proj.remove_track("v1")
    assert removed is True
    assert len(proj.tracks) == 1
    assert proj.tracks[0].track_id == "a1"


def test_project_add_clip() -> None:
    proj = make_project()
    proj.add_track(TimelineTrack(track_id="v1", name="V1", kind="video"))
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=5.0, position=0.0)
    ok = proj.add_clip("v1", clip)
    assert ok is True
    assert len(proj.tracks[0].clips) == 1


def test_project_add_clip_missing_track() -> None:
    proj = make_project()
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=5.0, position=0.0)
    assert proj.add_clip("nonexistent", clip) is False


def test_project_duration_seconds() -> None:
    proj = make_project()
    proj.add_track(TimelineTrack(track_id="v1", name="V1", kind="video"))
    proj.add_clip("v1", TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=10.0, position=5.0))
    # duration = position(5) + (out - in)(10) = 15
    assert proj.duration_seconds == pytest.approx(15.0)


def test_project_to_dict_round_trip() -> None:
    proj = make_project()
    proj.add_track(TimelineTrack(track_id="v1", name="V1", kind="video"))
    d = proj.to_dict()
    proj2 = KdenliveProject.from_dict(d)
    assert proj2.width == proj.width
    assert proj2.fps_num == proj.fps_num
    assert len(proj2.tracks) == 1
    assert proj2.tracks[0].track_id == "v1"


# ---------------------------------------------------------------------------
# Timeline CRUD


def test_timeline_add_video_track() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "Main")
    assert track.kind == "video"
    assert track.name == "Main"
    assert track in proj.tracks


def test_timeline_add_audio_track() -> None:
    proj = make_project()
    track = tl_mod.add_audio_track(proj, "Narration")
    assert track.kind == "audio"
    assert track in proj.tracks


def test_timeline_add_video_track_at_index() -> None:
    proj = make_project()
    t0 = tl_mod.add_video_track(proj, "First")
    t1 = tl_mod.add_video_track(proj, "Inserted", idx=0)
    assert proj.tracks[0] is t1
    assert proj.tracks[1] is t0


def test_timeline_remove_track() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "Temp")
    assert tl_mod.remove_track(proj, track.track_id) is True
    assert proj.tracks == []


def test_timeline_mute_lock() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    assert tl_mod.mute_track(proj, track.track_id, True) is True
    assert proj.tracks[0].muted is True
    assert tl_mod.lock_track(proj, track.track_id, True) is True
    assert proj.tracks[0].locked is True


def test_timeline_move_clip() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=5.0, position=0.0)
    proj.add_clip(track.track_id, clip)
    assert tl_mod.move_clip(proj, "c1", 10.0) is True
    assert proj.tracks[0].clips[0].position == pytest.approx(10.0)


def test_timeline_trim_clip() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=10.0, position=0.0)
    proj.add_clip(track.track_id, clip)
    assert tl_mod.trim_clip(proj, "c1", 2.0, 8.0) is True
    c = proj.tracks[0].clips[0]
    assert c.in_point == pytest.approx(2.0)
    assert c.out_point == pytest.approx(8.0)


def test_timeline_trim_invalid() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=10.0, position=0.0)
    proj.add_clip(track.track_id, clip)
    with pytest.raises(ValueError):
        tl_mod.trim_clip(proj, "c1", 8.0, 2.0)


def test_timeline_split_clip() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=20.0, position=0.0)
    proj.add_clip(track.track_id, clip)
    result = tl_mod.split_clip_at(proj, "c1", 10.0)
    assert result is not None
    left, right = result
    assert left.out_point == pytest.approx(10.0)
    assert right.in_point == pytest.approx(10.0)
    assert right.position == pytest.approx(10.0)
    assert len(proj.tracks[0].clips) == 2


def test_timeline_remove_clip() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=5.0, position=0.0)
    proj.add_clip(track.track_id, clip)
    assert tl_mod.remove_clip(proj, "c1") is True
    assert proj.tracks[0].clips == []


def test_timeline_get_clip_at() -> None:
    proj = make_project()
    track = tl_mod.add_video_track(proj, "V1")
    clip = TimelineClip(clip_id="c1", bin_id="bin1", in_point=0.0, out_point=10.0, position=5.0)
    proj.add_clip(track.track_id, clip)
    found = tl_mod.get_clip_at(proj, 7.0, track.track_id)
    assert found is not None
    assert found["clip_id"] == "c1"
    assert tl_mod.get_clip_at(proj, 20.0, track.track_id) is None


# ---------------------------------------------------------------------------
# Render profile listing


def test_render_profiles_not_empty() -> None:
    profiles = render_mod.list_render_profiles()
    assert len(profiles) >= 4
    assert "youtube_1080p" in profiles


def test_render_set_valid_profile() -> None:
    render_mod.set_render_profile("youtube_720p")
    assert render_mod._active_profile == "youtube_720p"
    render_mod.set_render_profile("youtube_1080p")


def test_render_set_invalid_profile() -> None:
    with pytest.raises(render_mod.RenderError):
        render_mod.set_render_profile("nonexistent_profile_xyz")


def test_render_estimate_size() -> None:
    size = render_mod.estimate_output_size("youtube_1080p", 60.0)
    assert size > 0


def test_render_range_invalid() -> None:
    with pytest.raises(render_mod.RenderError):
        render_mod.set_render_range(30.0, 10.0)


# ---------------------------------------------------------------------------
# Effect building


def test_effect_add_and_list() -> None:
    proj = make_project()
    eff = eff_mod.add_effect(proj, "clip_abc", "brightness", {"level": 1.2})
    assert eff["name"] == "brightness"
    assert eff["params"]["level"] == pytest.approx(1.2)
    effects = eff_mod.list_effects(proj, "clip_abc")
    assert len(effects) == 1
    assert effects[0]["effect_id"] == eff["effect_id"]


def test_effect_remove() -> None:
    proj = make_project()
    eff = eff_mod.add_effect(proj, "clip_abc", "contrast", {"level": 0.8})
    assert eff_mod.remove_effect(proj, "clip_abc", eff["effect_id"]) is True
    assert eff_mod.list_effects(proj, "clip_abc") == []


def test_effect_remove_nonexistent() -> None:
    proj = make_project()
    assert eff_mod.remove_effect(proj, "clip_abc", "eff_no_such") is False


def test_effect_set_param() -> None:
    proj = make_project()
    eff = eff_mod.add_effect(proj, "clip_x", "saturation", {"level": 1.0})
    ok = eff_mod.set_effect_param(proj, "clip_x", eff["effect_id"], "level", 0.5)
    assert ok is True
    updated = eff_mod.list_effects(proj, "clip_x")[0]
    assert updated["params"]["level"] == pytest.approx(0.5)


def test_transition_creation() -> None:
    proj = make_project()
    trans = eff_mod.add_transition(proj, "c1", "c2", "luma", 25)
    assert trans["from_clip"] == "c1"
    assert trans["to_clip"] == "c2"
    assert trans["duration_frames"] == 25


def test_title_clip_creation() -> None:
    proj = make_project()
    clip_id = eff_mod.add_title_clip(proj, "Hello World", 75, font="Helvetica")
    assert clip_id.startswith("title_")
    effects = eff_mod.list_effects(proj, clip_id)
    assert len(effects) == 1
    assert effects[0]["params"]["text"] == "Hello World"


# ---------------------------------------------------------------------------
# BinClip tests


def make_proj() -> KdenliveProject:
    return KdenliveProject(profile_name="hdv_1080_25p")


class TestBinClip:
    def test_import_clip(self) -> None:
        proj = make_proj()
        clip = bin_mod.import_clip(proj, "/media/video.mp4", name="My Video")
        assert clip["name"] == "My Video"
        assert clip["source_path"] == "/media/video.mp4"
        assert clip["clip_id"] == "C001"

    def test_import_auto_name(self) -> None:
        proj = make_proj()
        clip = bin_mod.import_clip(proj, "/media/clip.mp4")
        assert clip["name"] == "clip.mp4"

    def test_list_clips_empty(self) -> None:
        proj = make_proj()
        info = bin_mod.list_clips(proj)
        assert info["count"] == 0

    def test_list_clips_multiple(self) -> None:
        proj = make_proj()
        bin_mod.import_clip(proj, "/a.mp4")
        bin_mod.import_clip(proj, "/b.mp4")
        info = bin_mod.list_clips(proj)
        assert info["count"] == 2

    def test_remove_clip(self) -> None:
        proj = make_proj()
        clip = bin_mod.import_clip(proj, "/media/video.mp4")
        removed = bin_mod.remove_clip(proj, clip["clip_id"])
        assert removed["clip_id"] == clip["clip_id"]
        assert bin_mod.list_clips(proj)["count"] == 0

    def test_remove_missing_clip(self) -> None:
        proj = make_proj()
        with pytest.raises(KeyError):
            bin_mod.remove_clip(proj, "C999")

    def test_get_clip(self) -> None:
        proj = make_proj()
        clip = bin_mod.import_clip(proj, "/video.mp4")
        found = bin_mod.get_clip(proj, clip["clip_id"])
        assert found["source_path"] == "/video.mp4"

    def test_build_mlt_producer(self) -> None:
        proj = make_proj()
        clip = bin_mod.import_clip(proj, "/video.mp4", duration=10.0)
        attrs = bin_mod.build_mlt_producer(clip)
        assert attrs["id"] == "C001"
        assert attrs["resource"] == "/video.mp4"
        assert attrs["mlt_service"] == "avformat"

    def test_invalid_clip_type(self) -> None:
        from sven_integrations.kdenlive.core.bin import BinClip
        with pytest.raises(ValueError):
            BinClip(clip_id="X", name="x", source_path="/x", clip_type="unknown_type")


# ---------------------------------------------------------------------------
# Guide tests


class TestTimelineGuide:
    def test_add_guide(self) -> None:
        proj = make_proj()
        guide = guide_mod.add_guide(proj, 30.0, label="Chapter 1")
        assert guide["position_seconds"] == 30.0
        assert guide["label"] == "Chapter 1"
        assert guide["guide_id"] == 1

    def test_add_multiple_guides(self) -> None:
        proj = make_proj()
        guide_mod.add_guide(proj, 10.0, label="Start")
        guide_mod.add_guide(proj, 60.0, label="Mid")
        info = guide_mod.list_guides(proj)
        assert info["count"] == 2

    def test_list_guides_sorted(self) -> None:
        proj = make_proj()
        guide_mod.add_guide(proj, 60.0, label="B")
        guide_mod.add_guide(proj, 10.0, label="A")
        info = guide_mod.list_guides(proj)
        positions = [g["position_seconds"] for g in info["guides"]]
        assert positions == sorted(positions)

    def test_remove_guide(self) -> None:
        proj = make_proj()
        g = guide_mod.add_guide(proj, 30.0)
        guide_mod.remove_guide(proj, g["guide_id"])
        assert guide_mod.list_guides(proj)["count"] == 0

    def test_remove_missing_guide(self) -> None:
        proj = make_proj()
        with pytest.raises(KeyError):
            guide_mod.remove_guide(proj, 999)

    def test_build_guide_xml(self) -> None:
        proj = make_proj()
        g = guide_mod.add_guide(proj, 90.0, label="Credits", guide_type="chapter")
        xml_str = guide_mod.build_guide_xml(g)
        assert "<guide" in xml_str
        assert "Credits" in xml_str


# ---------------------------------------------------------------------------
# Kdenlive transition tests


class TestKdenliveTransitions:
    def test_add_transition(self) -> None:
        proj = make_proj()
        result = kd_trans_mod.add_transition(proj, "dissolve", "V1", "V2", 10.0, 1.5)
        assert result["transition_type"] == "dissolve"
        assert result["track_a"] == "V1"
        assert result["duration_seconds"] == pytest.approx(1.5)

    def test_add_invalid_transition(self) -> None:
        proj = make_proj()
        with pytest.raises(ValueError):
            kd_trans_mod.add_transition(proj, "sparkle", "V1", "V2", 0.0)

    def test_list_transitions(self) -> None:
        proj = make_proj()
        kd_trans_mod.add_transition(proj, "dissolve", "V1", "V2", 0.0)
        kd_trans_mod.add_transition(proj, "wipe", "V1", "V2", 5.0)
        info = kd_trans_mod.list_transitions(proj)
        assert info["count"] == 2

    def test_remove_transition(self) -> None:
        proj = make_proj()
        t = kd_trans_mod.add_transition(proj, "dissolve", "V1", "V2", 0.0)
        kd_trans_mod.remove_transition(proj, t["transition_id"])
        assert kd_trans_mod.list_transitions(proj)["count"] == 0

    def test_set_transition_param(self) -> None:
        proj = make_proj()
        t = kd_trans_mod.add_transition(proj, "dissolve", "V1", "V2", 0.0)
        updated = kd_trans_mod.set_transition(proj, t["transition_id"], "softness", 0.5)
        assert updated["params"]["softness"] == pytest.approx(0.5)

    def test_build_transition_xml(self) -> None:
        proj = make_proj()
        t = kd_trans_mod.add_transition(proj, "dissolve", "V1", "V2", 5.0, 2.0)
        xml_str = kd_trans_mod.build_transition_xml(t)
        assert "<transition" in xml_str
        assert "luma" in xml_str
