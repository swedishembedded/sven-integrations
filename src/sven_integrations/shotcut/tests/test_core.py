"""pytest — Shotcut harness core tests."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from sven_integrations.shotcut.core import compositing as comp_mod
from sven_integrations.shotcut.core import export as export_mod
from sven_integrations.shotcut.core import filters as filt_mod
from sven_integrations.shotcut.core import media as media_mod
from sven_integrations.shotcut.core import timeline as tl_mod
from sven_integrations.shotcut.core import transitions as sc_trans_mod
from sven_integrations.shotcut.project import (
    MltClip,
    MltTrack,
    ShotcutProject,
)

# ---------------------------------------------------------------------------
# ShotcutProject model


def make_project() -> ShotcutProject:
    return ShotcutProject(profile_name="atsc_1080p_25", width=1920, height=1080, fps=25.0)


def test_project_defaults() -> None:
    proj = make_project()
    assert proj.width == 1920
    assert proj.height == 1080
    assert proj.fps == 25.0
    assert proj.tracks == []
    assert proj.timeline_duration_frames == 0


def test_project_add_track() -> None:
    proj = make_project()
    track = MltTrack(track_id="t1", name="Main")
    proj.add_track(track)
    assert len(proj.tracks) == 1


def test_project_remove_track() -> None:
    proj = make_project()
    proj.add_track(MltTrack(track_id="t1", name="T1"))
    proj.add_track(MltTrack(track_id="t2", name="T2"))
    assert proj.remove_track("t1") is True
    assert len(proj.tracks) == 1
    assert proj.tracks[0].track_id == "t2"


def test_project_add_clip_to_track() -> None:
    proj = make_project()
    proj.add_track(MltTrack(track_id="t1", name="Main"))
    clip = MltClip(clip_id="c1", resource="video.mp4", in_point=0, out_point=250, position=0)
    assert proj.add_clip_to_track("t1", clip) is True
    assert len(proj.tracks[0].clips) == 1


def test_project_add_clip_missing_track() -> None:
    proj = make_project()
    clip = MltClip(clip_id="c1", resource="video.mp4", in_point=0, out_point=250, position=0)
    assert proj.add_clip_to_track("nonexistent", clip) is False


def test_project_find_clip() -> None:
    proj = make_project()
    proj.add_track(MltTrack(track_id="t1", name="Main"))
    clip = MltClip(clip_id="c1", resource="video.mp4", in_point=0, out_point=250, position=0)
    proj.add_clip_to_track("t1", clip)
    found = proj.find_clip("c1")
    assert found is not None
    assert found.resource == "video.mp4"
    assert proj.find_clip("no_such") is None


def test_project_duration_frames() -> None:
    proj = make_project()
    proj.add_track(MltTrack(track_id="t1", name="V1"))
    # clip at position=100, length=150 → ends at 250
    proj.add_clip_to_track(
        "t1",
        MltClip(clip_id="c1", resource="v.mp4", in_point=0, out_point=150, position=100),
    )
    assert proj.timeline_duration_frames == 250


def test_project_to_dict_round_trip() -> None:
    proj = make_project()
    proj.add_track(MltTrack(track_id="t1", name="Main"))
    d = proj.to_dict()
    proj2 = ShotcutProject.from_dict(d)
    assert proj2.width == 1920
    assert proj2.fps == 25.0
    assert len(proj2.tracks) == 1
    assert proj2.tracks[0].track_id == "t1"


def test_clip_to_dict_round_trip() -> None:
    clip = MltClip(clip_id="c1", resource="file.mp4", in_point=10, out_point=200, position=5)
    clip.filters = ["brightness", "contrast"]
    d = clip.to_dict()
    clip2 = MltClip.from_dict(d)
    assert clip2.clip_id == "c1"
    assert clip2.in_point == 10
    assert clip2.filters == ["brightness", "contrast"]


# ---------------------------------------------------------------------------
# MLT document building


def test_create_mlt_document() -> None:
    tree = tl_mod.create_mlt_document("atsc_1080p_25")
    root = tree.getroot()
    assert root.tag == "mlt"
    profile = root.find("profile")
    assert profile is not None
    assert profile.get("description") == "atsc_1080p_25"


def test_add_clip_to_playlist() -> None:
    root = ET.Element("mlt")
    playlist = ET.SubElement(root, "playlist", attrib={"id": "pl1"})
    entry = tl_mod.add_clip_to_playlist(playlist, "video.mp4", 0, 250)
    assert entry.tag == "entry"
    assert entry.get("producer") == "video.mp4"
    assert entry.get("in") == "0"
    assert entry.get("out") == "250"


def test_add_track_to_tractor() -> None:
    root = ET.Element("mlt")
    tractor = ET.SubElement(root, "tractor")
    track_elem = tl_mod.add_track_to_tractor(tractor, "pl1", hide=0)
    assert track_elem.tag == "track"
    assert track_elem.get("producer") == "pl1"


def test_build_transition() -> None:
    trans = tl_mod.build_transition(0, 1, 200, 25, "luma")
    assert trans.tag == "transition"
    props = {p.get("name"): p.text for p in trans.findall("property")}
    assert props["mlt_service"] == "luma"
    assert props["a_track"] == "0"
    assert props["b_track"] == "1"


def test_project_to_mlt_and_back(tmp_path) -> None:
    proj = make_project()
    proj.mlt_path = str(tmp_path / "test.mlt")
    proj.add_track(MltTrack(track_id="t1", name="Main"))
    proj.add_clip_to_track(
        "t1",
        MltClip(clip_id="c1", resource="video.mp4", in_point=0, out_point=250, position=0),
    )
    tree = tl_mod.project_to_mlt(proj)
    tl_mod.write_mlt(tree, proj.mlt_path)

    proj2 = tl_mod.mlt_to_project(proj.mlt_path)
    assert proj2.width == 1920
    assert len(proj2.tracks) == 1


# ---------------------------------------------------------------------------
# Filter element creation


def test_brightness_filter() -> None:
    filt = filt_mod.brightness_filter(1.3)
    assert filt.tag == "filter"
    props = {p.get("name"): p.text for p in filt.findall("property")}
    assert props["mlt_service"] == "brightness"
    assert props["level"] == "1.3"


def test_contrast_filter() -> None:
    filt = filt_mod.contrast_filter(0.9)
    props = {p.get("name"): p.text for p in filt.findall("property")}
    assert props["mlt_service"] == "contrast"


def test_blur_filter() -> None:
    filt = filt_mod.blur_filter(5.0)
    props = {p.get("name"): p.text for p in filt.findall("property")}
    assert props["mlt_service"] == "avfilter.gblur"
    assert props["sigma"] == "5.0"


def test_fade_in_filter() -> None:
    filt = filt_mod.fade_in_filter(25)
    assert filt.tag == "filter"
    assert filt.get("out") == "24"


def test_fade_out_filter() -> None:
    filt = filt_mod.fade_out_filter(25)
    assert filt.get("out") == "24"


def test_color_grading_filter() -> None:
    filt = filt_mod.color_grading_filter(lift=0.1, gamma=1.0, gain=0.9)
    props = {p.get("name"): p.text for p in filt.findall("property")}
    assert props["mlt_service"] == "lift_gamma_gain"
    assert "lift_r" in props


def test_attach_filter_to_clip() -> None:
    clip_elem = ET.Element("producer")
    filt = filt_mod.brightness_filter(1.0)
    filt_mod.attach_filter_to_clip(clip_elem, filt)
    assert len(clip_elem) == 1
    assert clip_elem[0].tag == "filter"


def test_build_filter_element_custom() -> None:
    filt = filt_mod.build_filter_element("frei0r.colorhalftone", {"dotRadius": "0.1"})
    props = {p.get("name"): p.text for p in filt.findall("property")}
    assert props["mlt_service"] == "frei0r.colorhalftone"
    assert props["dotRadius"] == "0.1"


# ---------------------------------------------------------------------------
# Melt command building


def test_list_melt_presets() -> None:
    presets = export_mod.list_melt_presets()
    assert len(presets) >= 4
    assert "youtube" in presets
    assert "prores" in presets


def test_build_melt_command_unknown_preset() -> None:
    from sven_integrations.shotcut.backend import ShotcutError

    with pytest.raises(ShotcutError):
        export_mod.build_melt_command("in.mlt", "out.mp4", "nonexistent_xyz")


def test_estimate_duration_nonexistent() -> None:
    result = export_mod.estimate_duration("/no/such/file.mlt")
    assert result == 0.0


def test_estimate_duration_valid(tmp_path) -> None:
    proj = make_project()
    proj.mlt_path = str(tmp_path / "test.mlt")
    proj.add_track(MltTrack(track_id="t1", name="V1"))
    proj.add_clip_to_track(
        "t1",
        MltClip(clip_id="c1", resource="v.mp4", in_point=0, out_point=250, position=0),
    )
    tree = tl_mod.project_to_mlt(proj)
    tl_mod.write_mlt(tree, proj.mlt_path)
    duration = export_mod.estimate_duration(proj.mlt_path)
    assert duration == pytest.approx(10.0)  # 250 frames / 25 fps = 10s


def test_get_supported_codecs() -> None:
    codecs = export_mod.get_supported_codecs()
    assert "video" in codecs
    assert "audio" in codecs
    assert isinstance(codecs["video"], list)
    assert isinstance(codecs["audio"], list)


# ---------------------------------------------------------------------------
# Compositing tests


def make_sc_project_with_tracks(n: int = 2) -> ShotcutProject:
    proj = ShotcutProject()
    for i in range(n):
        proj.add_track(MltTrack(track_id=f"t{i}", name=f"Track {i}"))
    return proj


class TestBlendModes:
    def test_list_blend_modes(self) -> None:
        modes = comp_mod.list_blend_modes()
        names = [m["name"] for m in modes]
        assert "normal" in names
        assert "multiply" in names
        assert "screen" in names
        assert len(modes) >= 17

    def test_set_track_blend_mode(self) -> None:
        proj = make_sc_project_with_tracks()
        result = comp_mod.set_track_blend_mode(proj, 0, "multiply")
        assert result["blend_mode"] == "multiply"

    def test_set_invalid_blend_mode(self) -> None:
        proj = make_sc_project_with_tracks()
        with pytest.raises(ValueError):
            comp_mod.set_track_blend_mode(proj, 0, "sparkle")

    def test_get_blend_mode_default(self) -> None:
        proj = make_sc_project_with_tracks()
        result = comp_mod.get_track_blend_mode(proj, 0)
        assert result["blend_mode"] == "normal"

    def test_set_track_opacity(self) -> None:
        proj = make_sc_project_with_tracks()
        result = comp_mod.set_track_opacity(proj, 1, 0.5)
        assert result["opacity"] == pytest.approx(0.5)

    def test_set_opacity_out_of_range(self) -> None:
        proj = make_sc_project_with_tracks()
        with pytest.raises(ValueError):
            comp_mod.set_track_opacity(proj, 0, 1.5)


# ---------------------------------------------------------------------------
# Media check tests (mocked filesystem)


class TestMediaCheck:
    def test_list_media_empty_project(self) -> None:
        proj = ShotcutProject()
        info = media_mod.list_media(proj)
        assert info["count"] == 0

    def test_list_media_deduplicates(self) -> None:
        proj = ShotcutProject()
        t = MltTrack(track_id="t0", name="T0")
        t.clips.append(MltClip(clip_id="c1", resource="/video.mp4", in_point=0, out_point=100, position=0))
        t.clips.append(MltClip(clip_id="c2", resource="/video.mp4", in_point=0, out_point=100, position=100))
        proj.add_track(t)
        info = media_mod.list_media(proj)
        assert info["count"] == 1

    def test_check_media_files_missing(self, tmp_path: "Path") -> None:
        proj = ShotcutProject()
        t = MltTrack(track_id="t0", name="T0")
        t.clips.append(MltClip(clip_id="c1", resource="/nonexistent/ghost.mp4", in_point=0, out_point=10, position=0))
        proj.add_track(t)
        result = media_mod.check_media_files(proj)
        assert result["ok"] is False
        assert "/nonexistent/ghost.mp4" in result["missing"]

    def test_check_media_files_all_ok(self, tmp_path: "Path") -> None:
        f = tmp_path / "clip.mp4"
        f.write_bytes(b"fake")
        proj = ShotcutProject()
        t = MltTrack(track_id="t0", name="T0")
        t.clips.append(MltClip(clip_id="c1", resource=str(f), in_point=0, out_point=10, position=0))
        proj.add_track(t)
        result = media_mod.check_media_files(proj)
        assert result["ok"] is True
        assert len(result["missing"]) == 0


# ---------------------------------------------------------------------------
# Shotcut transition tests


class TestShotcutTransitions:
    def test_transition_registry_not_empty(self) -> None:
        assert len(sc_trans_mod.TRANSITION_REGISTRY) >= 9

    def test_list_available_transitions(self) -> None:
        items = sc_trans_mod.list_available_transitions()
        names = [t["name"] for t in items]
        assert "dissolve" in names
        assert "barn_door" in names

    def test_list_available_by_category(self) -> None:
        wipes = sc_trans_mod.list_available_transitions(category="wipe")
        assert all(t["category"] == "wipe" for t in wipes)

    def test_add_transition(self) -> None:
        proj = ShotcutProject()
        result = sc_trans_mod.add_transition(proj, "dissolve", 0, 1, in_frame=100, out_frame=125)
        assert result["name"] == "dissolve"
        assert result["in_frame"] == 100

    def test_add_unknown_transition(self) -> None:
        proj = ShotcutProject()
        with pytest.raises(ValueError):
            sc_trans_mod.add_transition(proj, "sparkle", 0, 1, in_frame=0, out_frame=25)

    def test_add_invalid_frame_range(self) -> None:
        proj = ShotcutProject()
        with pytest.raises(ValueError):
            sc_trans_mod.add_transition(proj, "dissolve", 0, 1, in_frame=50, out_frame=25)

    def test_list_transitions(self) -> None:
        proj = ShotcutProject()
        sc_trans_mod.add_transition(proj, "dissolve", 0, 1, in_frame=0, out_frame=25)
        sc_trans_mod.add_transition(proj, "wipe_left", 0, 1, in_frame=100, out_frame=125)
        info = sc_trans_mod.list_transitions(proj)
        assert info["count"] == 2

    def test_remove_transition(self) -> None:
        proj = ShotcutProject()
        sc_trans_mod.add_transition(proj, "dissolve", 0, 1, in_frame=0, out_frame=25)
        sc_trans_mod.remove_transition(proj, 0)
        assert sc_trans_mod.list_transitions(proj)["count"] == 0

    def test_set_transition_param(self) -> None:
        proj = ShotcutProject()
        sc_trans_mod.add_transition(proj, "dissolve", 0, 1, in_frame=0, out_frame=25)
        result = sc_trans_mod.set_transition_param(proj, 0, "softness", 0.3)
        assert result["params"]["softness"] == pytest.approx(0.3)

    def test_build_transition_element(self) -> None:
        proj = ShotcutProject()
        t = sc_trans_mod.add_transition(proj, "dissolve", 0, 1, in_frame=0, out_frame=25)
        xml_str = sc_trans_mod.build_transition_element(t)
        assert "<transition" in xml_str
        assert "luma" in xml_str
