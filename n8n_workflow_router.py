"""N8N workflow router with templates and chaining utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowNode:
    """Represents an n8n workflow node."""

    name: str
    node_type: str
    parameters: Dict[str, Any]
    position: List[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.node_type,
            "parameters": self.parameters,
            "position": self.position,
        }


@dataclass
class WorkflowTemplate:
    """Template for generating workflow nodes."""

    name: str
    nodes: List[WorkflowNode] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "nodes": [node.to_dict() for node in self.nodes],
            "connections": self.connections,
            "active": False,
        }


@dataclass
class WorkflowChainer:
    """Handles conditional chaining between workflows."""

    def chain(self, templates: List[WorkflowTemplate]) -> WorkflowTemplate:
        """Chain templates sequentially with conditional routing."""
        if not templates:
            raise ValueError("No templates provided for chaining")
        combined_nodes: List[WorkflowNode] = []
        connections: Dict[str, Any] = {}
        offset_x = 0
        for template in templates:
            for node in template.nodes:
                combined_nodes.append(
                    WorkflowNode(
                        name=f"{template.name}-{node.name}",
                        node_type=node.node_type,
                        parameters=node.parameters,
                        position=[node.position[0] + offset_x, node.position[1]],
                    )
                )
            offset_x += 300
        for idx in range(len(combined_nodes) - 1):
            current = combined_nodes[idx].name
            nxt = combined_nodes[idx + 1].name
            connections.setdefault(current, {"main": []})
            connections[current]["main"].append([{"node": nxt, "type": "main", "index": 0}])
        return WorkflowTemplate(name="ChainedWorkflow", nodes=combined_nodes, connections=connections)


@dataclass
class N8NWorkflowManager:
    """Generates n8n-compatible workflow JSON templates."""

    def ingestion_template(self) -> WorkflowTemplate:
        trigger = WorkflowNode(
            name="WebhookTrigger",
            node_type="n8n-nodes-base.webhook",
            parameters={"httpMethod": "POST", "path": "ingest"},
            position=[0, 300],
        )
        processor = WorkflowNode(
            name="NormalizePayload",
            node_type="n8n-nodes-base.set",
            parameters={"keepOnlySet": True, "values": {"string": [{"name": "source", "value": "{{$json[\"source\"]}}"}]}},
            position=[200, 300],
        )
        connections = {"WebhookTrigger": {"main": [[{"node": "NormalizePayload", "type": "main", "index": 0}]]}}
        return WorkflowTemplate(name="DataIngestion", nodes=[trigger, processor], connections=connections)

    def ai_routing_template(self) -> WorkflowTemplate:
        router = WorkflowNode(
            name="AIRouter",
            node_type="n8n-nodes-base.switch",
            parameters={"dataType": "string", "rules": [{"operation": "contains", "value1": "{{$json[\"model\"]}}", "value2": "gpt"}]},
            position=[0, 200],
        )
        handler = WorkflowNode(
            name="CallModel",
            node_type="n8n-nodes-base.httpRequest",
            parameters={"url": "https://api.example.ai/execute", "method": "POST"},
            position=[250, 200],
        )
        connections = {"AIRouter": {"main": [[{"node": "CallModel", "type": "main", "index": 0}]]}}
        return WorkflowTemplate(name="ModelRouting", nodes=[router, handler], connections=connections)

    def webhook_template(self) -> WorkflowTemplate:
        webhook = WorkflowNode(
            name="OutboundWebhook",
            node_type="n8n-nodes-base.httpRequest",
            parameters={"url": "https://hooks.example.com/notify", "method": "POST"},
            position=[0, 150],
        )
        return WorkflowTemplate(name="WebhookDispatch", nodes=[webhook])

    def email_template(self) -> WorkflowTemplate:
        email = WorkflowNode(
            name="SendEmail",
            node_type="n8n-nodes-base.emailSend",
            parameters={"to": "ops@example.com", "subject": "Workflow Alert", "text": "{{$json[\"message\"]}}"},
            position=[0, 100],
        )
        return WorkflowTemplate(name="EmailAlert", nodes=[email])

    def database_sync_template(self) -> WorkflowTemplate:
        sync = WorkflowNode(
            name="DatabaseSync",
            node_type="n8n-nodes-base.postgres",
            parameters={"operation": "insert", "schema": "public", "table": "events"},
            position=[0, 50],
        )
        return WorkflowTemplate(name="DatabaseSync", nodes=[sync])

    def export(self, template: WorkflowTemplate, path: Path) -> None:
        """Export workflow template as an n8n JSON file."""
        payload = template.to_dict()
        path.write_text(json.dumps(payload, indent=2))

    def generate_bundle(self, output_dir: Path) -> List[Path]:
        """Generate all standard workflows and export them."""
        output_dir.mkdir(parents=True, exist_ok=True)
        templates = [
            self.ingestion_template(),
            self.ai_routing_template(),
            self.webhook_template(),
            self.email_template(),
            self.database_sync_template(),
        ]
        paths = []
        for template in templates:
            path = output_dir / f"{template.name}.json"
            self.export(template, path)
            paths.append(path)
        return paths

    def chain_with_error_handling(self, templates: List[WorkflowTemplate]) -> WorkflowTemplate:
        """Chain templates and add error handling nodes."""
        chainer = WorkflowChainer()
        chained = chainer.chain(templates)
        error_node = WorkflowNode(
            name="ErrorHandler",
            node_type="n8n-nodes-base.errorTrigger",
            parameters={"retryOnFail": True},
            position=[-200, 0],
        )
        chained.nodes.append(error_node)
        chained.connections.setdefault("ErrorHandler", {"main": []})
        return chained

