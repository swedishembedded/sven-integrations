"""Kdenlive timeline operations — XML-based when DBus is unavailable."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from typing import Any

from ..project import KdenliveProject, TimelineClip, TimelineTrack

# ---------------------------------------------------------------------------
# Public timeline API


def add_video_track(
    project: KdenliveProject,
    name: str,
    idx: int | None = None,
) -> TimelineTrack:
    """Insert a new video track and return it."""
    track = TimelineTrack(
        track_id=f"video_{uuid.uuid4().hex[:8]}",
        name=name,
        kind="video",
    )
    if idx is None:
        project.tracks.append(track)
    else:
        project.tracks.insert(idx, track)
    return track


def add_audio_track(
    project: KdenliveProject,
    name: str,
    idx: int | None = None,
) -> TimelineTrack:
    """Insert a new audio track and return it."""
    track = TimelineTrack(
        track_id=f"audio_{uuid.uuid4().hex[:8]}",
        name=name,
        kind="audio",
    )
    if idx is None:
        project.tracks.append(track)
    else:
        project.tracks.insert(idx, track)
    return track


def remove_track(project: KdenliveProject, track_id: str) -> bool:
    """Remove the track with the given ID.  Returns True if found."""
    return project.remove_track(track_id)


def lock_track(project: KdenliveProject, track_id: str, locked: bool) -> bool:
    """Set the locked state of a track."""
    for track in project.tracks:
        if track.track_id == track_id:
            track.locked = locked
            return True
    return False


def mute_track(project: KdenliveProject, track_id: str, muted: bool) -> bool:
    """Set the muted state of a track."""
    for track in project.tracks:
        if track.track_id == track_id:
            track.muted = muted
            return True
    return False


def move_clip(
    project: KdenliveProject,
    clip_id: str,
    new_position: float,
) -> bool:
    """Reposition a clip on the timeline.  Returns True if found."""
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_id == clip_id:
                clip.position = new_position
                return True
    return False


def trim_clip(
    project: KdenliveProject,
    clip_id: str,
    new_in: float,
    new_out: float,
) -> bool:
    """Adjust a clip's source in/out points."""
    if new_in >= new_out:
        raise ValueError(f"in_point ({new_in}) must be less than out_point ({new_out})")
    for track in project.tracks:
        for clip in track.clips:
            if clip.clip_id == clip_id:
                clip.in_point = new_in
                clip.out_point = new_out
                return True
    return False


def split_clip_at(
    project: KdenliveProject,
    clip_id: str,
    split_pos: float,
) -> tuple[TimelineClip, TimelineClip] | None:
    """Split a clip at *split_pos* (timeline seconds).

    Returns a tuple (left_clip, right_clip) or None if the clip was not found
    or *split_pos* falls outside the clip.
    """
    for track in project.tracks:
        for i, clip in enumerate(track.clips):
            clip_end = clip.position + (clip.out_point - clip.in_point) / max(clip.speed, 1e-9)
            if clip.position <= split_pos < clip_end:
                split_source = clip.in_point + (split_pos - clip.position) * clip.speed

                left = TimelineClip(
                    clip_id=clip.clip_id,
                    bin_id=clip.bin_id,
                    in_point=clip.in_point,
                    out_point=split_source,
                    position=clip.position,
                    speed=clip.speed,
                )
                right = TimelineClip(
                    clip_id=f"clip_{uuid.uuid4().hex[:8]}",
                    bin_id=clip.bin_id,
                    in_point=split_source,
                    out_point=clip.out_point,
                    position=split_pos,
                    speed=clip.speed,
                )
                track.clips[i] = left
                track.clips.insert(i + 1, right)
                return left, right
    return None


def remove_clip(project: KdenliveProject, clip_id: str) -> bool:
    """Remove a clip from any track.  Returns True if found."""
    for track in project.tracks:
        for i, clip in enumerate(track.clips):
            if clip.clip_id == clip_id:
                del track.clips[i]
                return True
    return False


def get_clip_at(
    project: KdenliveProject,
    position: float,
    track_id: str,
) -> dict[str, Any] | None:
    """Return the clip dict at *position* seconds on *track_id*, or None."""
    for track in project.tracks:
        if track.track_id != track_id:
            continue
        for clip in track.clips:
            duration = (clip.out_point - clip.in_point) / max(clip.speed, 1e-9)
            if clip.position <= position < clip.position + duration:
                return clip.to_dict()
    return None


# ---------------------------------------------------------------------------
# XML round-trip helpers


def load_project_from_xml(path: str) -> KdenliveProject:
    """Parse a .kdenlive XML file into a KdenliveProject."""
    tree = ET.parse(path)
    root = tree.getroot()

    proj = KdenliveProject(project_path=path)

    # Read profile attributes from the <profile> element
    profile_elem = root.find("profile")
    if profile_elem is not None:
        proj.profile_name = profile_elem.get("description", proj.profile_name)
        try:
            proj.fps_num = int(profile_elem.get("frame_rate_num", proj.fps_num))
            proj.fps_den = int(profile_elem.get("frame_rate_den", proj.fps_den))
            proj.width = int(profile_elem.get("width", proj.width))
            proj.height = int(profile_elem.get("height", proj.height))
        except (ValueError, TypeError):
            pass

    # Parse tracks from the <tractor> element
    tractor = root.find("tractor")
    if tractor is not None:
        for track_elem in tractor.findall("track"):
            track_id = track_elem.get("producer", f"track_{uuid.uuid4().hex[:8]}")
            playlist_elem = root.find(f"./playlist[@id='{track_id}']")
            kind = "audio" if "audio" in track_id.lower() else "video"
            track = TimelineTrack(track_id=track_id, name=track_id, kind=kind)

            if playlist_elem is not None:
                for entry in playlist_elem.findall("entry"):
                    try:
                        clip = TimelineClip(
                            clip_id=f"clip_{uuid.uuid4().hex[:8]}",
                            bin_id=entry.get("producer", ""),
                            in_point=int(entry.get("in", 0)) / max(proj.fps_num, 1),
                            out_point=int(entry.get("out", 0)) / max(proj.fps_num, 1),
                            position=0.0,
                        )
                        track.clips.append(clip)
                    except (ValueError, TypeError):
                        pass

            proj.tracks.append(track)

    return proj


def save_project_to_xml(project: KdenliveProject, path: str) -> None:
    """Write a KdenliveProject to a minimal .kdenlive XML file."""
    root = ET.Element("mlt", attrib={"version": "7.0", "LC_NUMERIC": "C"})

    # Profile
    ET.SubElement(
        root,
        "profile",
        attrib={
            "description": project.profile_name,
            "frame_rate_num": str(project.fps_num),
            "frame_rate_den": str(project.fps_den),
            "width": str(project.width),
            "height": str(project.height),
            "progressive": "1",
            "sample_aspect_num": "1",
            "sample_aspect_den": "1",
            "display_aspect_num": str(project.width),
            "display_aspect_den": str(project.height),
            "colorspace": "709",
        },
    )

    # Playlists + tractor
    tractor = ET.SubElement(root, "tractor", attrib={"id": "maintractor"})
    for track in project.tracks:
        playlist = ET.SubElement(root, "playlist", attrib={"id": track.track_id})
        fps = project.fps_num / max(project.fps_den, 1)
        for clip in track.clips:
            ET.SubElement(
                playlist,
                "entry",
                attrib={
                    "producer": clip.bin_id,
                    "in": str(int(clip.in_point * fps)),
                    "out": str(int(clip.out_point * fps)),
                },
            )
        ET.SubElement(tractor, "track", attrib={"producer": track.track_id})

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)
