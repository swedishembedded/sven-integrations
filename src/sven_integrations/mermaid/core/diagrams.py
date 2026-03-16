"""Mermaid diagram syntax builders."""

from __future__ import annotations

from typing import Any


def build_flowchart(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    direction: str = "TB",
) -> str:
    """Build a flowchart diagram.

    Each node dict: {"id": str, "label": str, "shape": "rect"|"round"|"diamond"|"circle"}
    Each edge dict: {"from": str, "to": str, "label": str (optional), "arrow": "-->" (optional)}
    direction: TB|LR|BT|RL
    """
    valid_directions = {"TB", "LR", "BT", "RL", "TD"}
    dir_str = direction.upper() if direction.upper() in valid_directions else "TB"

    lines: list[str] = [f"flowchart {dir_str}"]

    shape_open = {"rect": "[", "round": "(", "diamond": "{", "circle": "((", "default": "["}
    shape_close = {"rect": "]", "round": ")", "diamond": "}", "circle": "))", "default": "]"}

    for node in nodes:
        node_id = node["id"]
        label = node.get("label", node_id)
        shape = node.get("shape", "rect")
        open_br = shape_open.get(shape, "[")
        close_br = shape_close.get(shape, "]")
        lines.append(f'    {node_id}{open_br}"{label}"{close_br}')

    for edge in edges:
        src = edge["from"]
        tgt = edge["to"]
        arrow = edge.get("arrow", "-->")
        label = edge.get("label", "")
        if label:
            lines.append(f'    {src} {arrow}|"{label}"| {tgt}')
        else:
            lines.append(f"    {src} {arrow} {tgt}")

    return "\n".join(lines)


def build_sequence(
    participants: list[str],
    messages: list[dict[str, Any]],
) -> str:
    """Build a sequenceDiagram.

    Each message dict: {"from": str, "to": str, "text": str, "type": "->>" (optional), "note": str (optional)}
    """
    lines: list[str] = ["sequenceDiagram"]
    for p in participants:
        lines.append(f"    participant {p}")
    for msg in messages:
        src = msg["from"]
        tgt = msg["to"]
        text = msg.get("text", "")
        arrow = msg.get("type", "->>")
        lines.append(f"    {src}{arrow}{tgt}: {text}")
        if "note" in msg:
            lines.append(f"    Note over {src},{tgt}: {msg['note']}")
    return "\n".join(lines)


def build_class_diagram(
    classes: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> str:
    """Build a classDiagram.

    Each class dict: {"name": str, "attributes": list[str], "methods": list[str]}
    Each relationship dict: {"from": str, "to": str, "type": "<|--|" etc., "label": str (optional)}
    """
    lines: list[str] = ["classDiagram"]
    for cls in classes:
        name = cls["name"]
        lines.append(f"    class {name} {{")
        for attr in cls.get("attributes", []):
            lines.append(f"        {attr}")
        for method in cls.get("methods", []):
            lines.append(f"        {method}()")
        lines.append("    }")
    for rel in relationships:
        src = rel["from"]
        tgt = rel["to"]
        rel_type = rel.get("type", "<|--")
        label = rel.get("label", "")
        if label:
            lines.append(f'    {src} {rel_type} {tgt} : {label}')
        else:
            lines.append(f"    {src} {rel_type} {tgt}")
    return "\n".join(lines)


def build_gantt(
    title: str,
    sections: list[dict[str, Any]],
) -> str:
    """Build a gantt diagram.

    Each section dict: {"title": str, "tasks": list[dict]}
    Each task dict: {"name": str, "status": "done"|"active"|"crit" (optional), "id": str (optional), "start": str, "end": str|"duration"}
    """
    lines: list[str] = [
        "gantt",
        f"    title {title}",
        "    dateFormat  YYYY-MM-DD",
    ]
    for section in sections:
        lines.append(f"    section {section['title']}")
        for task in section.get("tasks", []):
            name = task["name"]
            status = task.get("status", "")
            task_id = task.get("id", "")
            start = task.get("start", "")
            end = task.get("end", "1d")
            parts = [name + "  :"]
            if status:
                parts.append(status + ",")
            if task_id:
                parts.append(task_id + ",")
            if start:
                parts.append(start + ",")
            parts.append(end)
            lines.append("    " + " ".join(parts))
    return "\n".join(lines)


def build_pie(title: str, slices: list[tuple[str, float]]) -> str:
    """Build a pie chart.

    slices: list of (label, value) tuples.
    """
    lines: list[str] = [f'pie title {title}']
    for label, value in slices:
        lines.append(f'    "{label}" : {value}')
    return "\n".join(lines)


def build_state_diagram(
    states: list[str],
    transitions: list[dict[str, Any]],
) -> str:
    """Build a stateDiagram-v2.

    Each transition dict: {"from": str, "to": str, "label": str (optional)}
    Use "__start__" / "__end__" for [*] pseudostates.
    """
    lines: list[str] = ["stateDiagram-v2"]
    for state in states:
        lines.append(f"    {state}")
    for tr in transitions:
        src = "[*]" if tr["from"] == "__start__" else tr["from"]
        tgt = "[*]" if tr["to"] == "__end__" else tr["to"]
        label = tr.get("label", "")
        if label:
            lines.append(f"    {src} --> {tgt} : {label}")
        else:
            lines.append(f"    {src} --> {tgt}")
    return "\n".join(lines)


def build_er_diagram(
    entities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> str:
    """Build an erDiagram.

    Each entity dict: {"name": str, "attributes": list[dict{"type": str, "name": str, "key": bool}]}
    Each relationship dict: {"from": str, "to": str, "relation": str, "label": str}
    Relation example: "||--o{"
    """
    lines: list[str] = ["erDiagram"]
    for entity in entities:
        name = entity["name"]
        attrs = entity.get("attributes", [])
        if attrs:
            lines.append(f"    {name} {{")
            for attr in attrs:
                key_marker = " PK" if attr.get("key") else ""
                lines.append(f'        {attr["type"]} {attr["name"]}{key_marker}')
            lines.append("    }")
        else:
            lines.append(f"    {name} {{}}")
    for rel in relationships:
        src = rel["from"]
        tgt = rel["to"]
        relation = rel.get("relation", "||--||")
        label = rel.get("label", "relates")
        lines.append(f'    {src} {relation} {tgt} : "{label}"')
    return "\n".join(lines)
