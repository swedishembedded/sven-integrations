"""ComfyUI workflow and project models."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowNode:
    node_id: str
    class_type: str
    title: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "class_type": self.class_type,
            "title": self.title,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WorkflowNode":
        return cls(
            node_id=d["node_id"],
            class_type=d["class_type"],
            title=d.get("title"),
            inputs=dict(d.get("inputs", {})),
            outputs=list(d.get("outputs", [])),
        )


@dataclass
class NodeConnection:
    from_node: str
    from_slot: int
    to_node: str
    to_slot: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "from_slot": self.from_slot,
            "to_node": self.to_node,
            "to_slot": self.to_slot,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NodeConnection":
        return cls(
            from_node=d["from_node"],
            from_slot=int(d["from_slot"]),
            to_node=d["to_node"],
            to_slot=int(d["to_slot"]),
        )


@dataclass
class ComfyWorkflow:
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled"
    nodes: dict[str, WorkflowNode] = field(default_factory=dict)
    connections: list[NodeConnection] = field(default_factory=list)

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes[node.node_id] = node

    def remove_node(self, node_id: str) -> bool:
        if node_id not in self.nodes:
            return False
        del self.nodes[node_id]
        self.connections = [
            c
            for c in self.connections
            if c.from_node != node_id and c.to_node != node_id
        ]
        return True

    def connect_nodes(
        self,
        from_node: str,
        from_slot: int,
        to_node: str,
        to_slot: int,
    ) -> None:
        self.connections.append(
            NodeConnection(
                from_node=from_node,
                from_slot=from_slot,
                to_node=to_node,
                to_slot=to_slot,
            )
        )

    def disconnect_nodes(
        self,
        from_node: str,
        from_slot: int,
        to_node: str,
        to_slot: int,
    ) -> bool:
        before = len(self.connections)
        self.connections = [
            c
            for c in self.connections
            if not (
                c.from_node == from_node
                and c.from_slot == from_slot
                and c.to_node == to_node
                and c.to_slot == to_slot
            )
        ]
        return len(self.connections) < before

    def find_node(self, node_id: str) -> WorkflowNode | None:
        return self.nodes.get(node_id)

    def validate(self) -> list[str]:
        """Return a list of validation errors."""
        errors: list[str] = []
        if not self.nodes:
            errors.append("Workflow has no nodes")
        node_ids = set(self.nodes.keys())
        for conn in self.connections:
            if conn.from_node not in node_ids:
                errors.append(f"Connection references unknown source node: {conn.from_node!r}")
            if conn.to_node not in node_ids:
                errors.append(f"Connection references unknown target node: {conn.to_node!r}")
        return errors

    def to_api_format(self) -> dict[str, Any]:
        """Convert to ComfyUI prompt API format.

        Each node becomes a top-level entry keyed by node_id.
        Connections are embedded as [node_id, slot] references in inputs.
        """
        prompt: dict[str, Any] = {}

        # Build a lookup: (to_node, to_slot) -> [from_node, from_slot]
        wire_map: dict[tuple[str, int], list[Any]] = {}
        for conn in self.connections:
            wire_map[(conn.to_node, conn.to_slot)] = [conn.from_node, conn.from_slot]

        for node_id, node in self.nodes.items():
            node_inputs: dict[str, Any] = dict(node.inputs)
            # Inject wired inputs as [node_id, slot_index] arrays
            for (tgt_node, tgt_slot), src in wire_map.items():
                if tgt_node == node_id:
                    # Find which input key corresponds to this slot
                    input_keys = list(node.inputs.keys())
                    if tgt_slot < len(input_keys):
                        node_inputs[input_keys[tgt_slot]] = src
            prompt[node_id] = {
                "class_type": node.class_type,
                "inputs": node_inputs,
            }
            if node.title:
                prompt[node_id]["_meta"] = {"title": node.title}
        return prompt

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "connections": [c.to_dict() for c in self.connections],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ComfyWorkflow":
        return cls(
            workflow_id=d.get("workflow_id", str(uuid.uuid4())),
            name=d.get("name", "Untitled"),
            nodes={
                k: WorkflowNode.from_dict(v) for k, v in d.get("nodes", {}).items()
            },
            connections=[NodeConnection.from_dict(c) for c in d.get("connections", [])],
        )


@dataclass
class ComfyProject:
    name: str = "default"
    server_url: str = "http://127.0.0.1:8188"
    workflows: list[ComfyWorkflow] = field(default_factory=list)
    active_workflow: str | None = None

    def add_workflow(self, workflow: ComfyWorkflow) -> None:
        self.workflows.append(workflow)
        if self.active_workflow is None:
            self.active_workflow = workflow.name

    def get_active_workflow(self) -> ComfyWorkflow | None:
        if self.active_workflow is None:
            return None
        for wf in self.workflows:
            if wf.name == self.active_workflow:
                return wf
        return None

    def set_active_workflow(self, name: str) -> bool:
        for wf in self.workflows:
            if wf.name == name:
                self.active_workflow = name
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "server_url": self.server_url,
            "workflows": [wf.to_dict() for wf in self.workflows],
            "active_workflow": self.active_workflow,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ComfyProject":
        return cls(
            name=d.get("name", "default"),
            server_url=d.get("server_url", "http://127.0.0.1:8188"),
            workflows=[ComfyWorkflow.from_dict(w) for w in d.get("workflows", [])],
            active_workflow=d.get("active_workflow"),
        )
