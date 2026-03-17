"""Shotcut / MLT XML timeline builder."""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET

from ..project import MltClip, MltTrack, ShotcutProject

# ---------------------------------------------------------------------------
# Document creation


def create_mlt_document(profile: str = "atsc_1080p_25") -> ET.ElementTree:
    """Return a skeleton MLT ElementTree with a profile element."""
    root = ET.Element("mlt", attrib={"version": "7.0", "LC_NUMERIC": "C"})
    ET.SubElement(root, "profile", attrib={"description": profile})
    return ET.ElementTree(root)


# ---------------------------------------------------------------------------
# Playlist helpers


def add_clip_to_playlist(
    playlist_elem: ET.Element,
    resource: str,
    in_f: int,
    out_f: int,
) -> ET.Element:
    """Append an <entry> to a <playlist> element and return it."""
    clip_id = f"clip_{uuid.uuid4().hex[:8]}"
    entry = ET.SubElement(
        playlist_elem,
        "entry",
        attrib={
            "producer": resource,
            "in": str(in_f),
            "out": str(out_f),
            "id": clip_id,
        },
    )
    return entry


# ---------------------------------------------------------------------------
# Tractor helpers


def add_track_to_tractor(
    tractor_elem: ET.Element,
    playlist_id: str,
    hide: int = 0,
) -> ET.Element:
    """Add a <track> reference to a <tractor> element."""
    attrib: dict[str, str] = {"producer": playlist_id}
    if hide:
        attrib["hide"] = "video" if hide == 1 else "audio"
    track = ET.SubElement(tractor_elem, "track", attrib=attrib)
    return track


# ---------------------------------------------------------------------------
# Transition helpers


def build_transition(
    from_track: int,
    to_track: int,
    start_f: int,
    length_f: int,
    transition_type: str = "luma",
) -> ET.Element:
    """Create a <transition> element."""
    trans = ET.Element(
        "transition",
        attrib={
            "in": str(start_f),
            "out": str(start_f + length_f - 1),
        },
    )
    _property(trans, "a_track", str(from_track))
    _property(trans, "b_track", str(to_track))
    _property(trans, "mlt_service", transition_type)
    return trans


def _property(parent: ET.Element, name: str, value: str) -> ET.Element:
    elem = ET.SubElement(parent, "property", attrib={"name": name})
    elem.text = value
    return elem


# ---------------------------------------------------------------------------
# Document serialisation


def write_mlt(tree: ET.ElementTree, path: str) -> None:
    """Write an MLT ElementTree to *path* with pretty indentation."""
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)


# ---------------------------------------------------------------------------
# High-level project → XML


def project_to_mlt(project: ShotcutProject) -> ET.ElementTree:
    """Convert a ShotcutProject to an MLT ElementTree.

    Creates producer elements for each unique resource so melt can resolve references.
    """
    root = ET.Element(
        "mlt",
        attrib={
            "version": "7.0",
            "LC_NUMERIC": "C",
            "title": project.mlt_path or "untitled",
        },
    )

    # Collect unique resources and create producers (required for melt)
    resources: set[str] = set()
    for track in project.tracks:
        for clip in track.clips:
            resources.add(clip.resource)

    for resource in resources:
        prod = ET.SubElement(root, "producer", attrib={"id": resource})
        ET.SubElement(prod, "property", attrib={"name": "resource"}).text = resource
        # For color/generated sources, set mlt_service
        if resource.startswith("color:"):
            prod.set("mlt_service", "color")
        elif resource.startswith("count:"):
            prod.set("mlt_service", "count")

    # Profile
    ET.SubElement(
        root,
        "profile",
        attrib={
            "description": project.profile_name,
            "width": str(project.width),
            "height": str(project.height),
            "frame_rate_num": str(int(project.fps)),
            "frame_rate_den": "1",
            "progressive": "1",
            "sample_aspect_num": "1",
            "sample_aspect_den": "1",
            "display_aspect_num": str(project.width),
            "display_aspect_den": str(project.height),
            "colorspace": "709",
        },
    )

    tractor = ET.SubElement(root, "tractor", attrib={"id": "maintractor"})

    for track in project.tracks:
        playlist_elem = ET.SubElement(root, "playlist", attrib={"id": track.track_id})
        for clip in track.clips:
            ET.SubElement(
                playlist_elem,
                "entry",
                attrib={
                    "producer": clip.resource,
                    "in": str(clip.in_point),
                    "out": str(clip.out_point),
                    "id": clip.clip_id,
                },
            )
        attrib: dict[str, str] = {"producer": track.track_id}
        if track.hide:
            attrib["hide"] = "video" if track.hide == 1 else "audio"
        ET.SubElement(tractor, "track", attrib=attrib)

    return ET.ElementTree(root)


def mlt_to_project(path: str) -> ShotcutProject:
    """Parse an MLT file into a ShotcutProject."""
    tree = ET.parse(path)
    root = tree.getroot()
    proj = ShotcutProject(mlt_path=path)

    profile_elem = root.find("profile")
    if profile_elem is not None:
        proj.profile_name = profile_elem.get("description", proj.profile_name)
        try:
            proj.width = int(profile_elem.get("width", proj.width))
            proj.height = int(profile_elem.get("height", proj.height))
            fn = int(profile_elem.get("frame_rate_num", int(proj.fps)))
            fd = int(profile_elem.get("frame_rate_den", 1))
            proj.fps = fn / max(fd, 1)
        except (ValueError, TypeError):
            pass

    tractor = root.find("tractor")
    if tractor is not None:
        for track_elem in tractor.findall("track"):
            pid = track_elem.get("producer", "")
            hide_attr = track_elem.get("hide", "")
            hide_int = 0
            if hide_attr == "video":
                hide_int = 1
            elif hide_attr == "audio":
                hide_int = 2

            playlist_elem = root.find(f"./playlist[@id='{pid}']")
            track = MltTrack(track_id=pid, name=pid, hide=hide_int)

            if playlist_elem is not None:
                position = 0
                for entry in playlist_elem.findall("entry"):
                    try:
                        in_f = int(entry.get("in", 0))
                        out_f = int(entry.get("out", 0))
                        clip = MltClip(
                            clip_id=entry.get("id", f"clip_{uuid.uuid4().hex[:8]}"),
                            resource=entry.get("producer", ""),
                            in_point=in_f,
                            out_point=out_f,
                            position=position,
                        )
                        position += out_f - in_f
                        track.clips.append(clip)
                    except (ValueError, TypeError):
                        pass

            proj.tracks.append(track)

    return proj
