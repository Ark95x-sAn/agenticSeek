"""
N8N Workflow Router - Automated Workflow Generation and Management

This module provides:
- N8NWorkflowManager for generating n8n-compatible workflow JSON
- Templates for data ingestion, AI model routing, webhooks, email, database sync
- WorkflowChainer with conditional branching and error handling
- Exportable n8n JSON files for direct import
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NodeType(Enum):
    """N8N Node Types"""
    WEBHOOK = "n8n-nodes-base.webhook"
    HTTP_REQUEST = "n8n-nodes-base.httpRequest"
    SET = "n8n-nodes-base.set"
    IF = "n8n-nodes-base.if"
    SWITCH = "n8n-nodes-base.switch"
    FUNCTION = "n8n-nodes-base.function"
    EMAIL = "n8n-nodes-base.emailSend"
    DATABASE = "n8n-nodes-base.postgres"
    MYSQL = "n8n-nodes-base.mySql"
    MONGODB = "n8n-nodes-base.mongoDb"
    SCHEDULE = "n8n-nodes-base.scheduleTrigger"
    CODE = "n8n-nodes-base.code"
    MERGE = "n8n-nodes-base.merge"
    SPLIT = "n8n-nodes-base.splitInBatches"
    ERROR_TRIGGER = "n8n-nodes-base.errorTrigger"
    EXECUTE_WORKFLOW = "n8n-nodes-base.executeWorkflow"


class TriggerType(Enum):
    """Workflow trigger types"""
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    EMAIL = "email"
    ERROR = "error"


@dataclass
class NodePosition:
    """Position of node in n8n canvas"""
    x: float
    y: float

    def to_list(self) -> List[float]:
        return [self.x, self.y]


@dataclass
class NodeParameter:
    """Node parameter configuration"""
    name: str
    value: Any
    type: str = "string"


@dataclass
class N8NNode:
    """N8N Workflow Node"""
    id: str
    name: str
    type: NodeType
    position: NodePosition
    parameters: Dict[str, Any] = field(default_factory=dict)
    credentials: Optional[Dict[str, Any]] = None
    disabled: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to n8n JSON format"""
        node_dict = {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "typeVersion": 1,
            "position": self.position.to_list(),
            "parameters": self.parameters,
            "disabled": self.disabled
        }

        if self.credentials:
            node_dict["credentials"] = self.credentials

        if self.notes:
            node_dict["notes"] = self.notes

        return node_dict


@dataclass
class N8NConnection:
    """Connection between nodes"""
    source_node: str
    source_output: int
    target_node: str
    target_input: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert connection to n8n format"""
        return {
            "node": self.source_node,
            "type": "main",
            "index": self.source_output
        }


@dataclass
class N8NWorkflow:
    """Complete N8N Workflow"""
    id: str
    name: str
    nodes: List[N8NNode] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)
    active: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def add_node(self, node: N8NNode) -> None:
        """Add a node to the workflow"""
        self.nodes.append(node)
        logger.info(f"Added node: {node.name} ({node.type.value})")

    def connect_nodes(self, source: str, target: str,
                     source_output: int = 0, target_input: int = 0) -> None:
        """Connect two nodes"""
        if source not in self.connections:
            self.connections[source] = {"main": []}

        # Ensure we have enough output arrays
        while len(self.connections[source]["main"]) <= source_output:
            self.connections[source]["main"].append([])

        connection = {
            "node": target,
            "type": "main",
            "index": target_input
        }

        self.connections[source]["main"][source_output].append(connection)
        logger.info(f"Connected {source} -> {target}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to n8n JSON format"""
        return {
            "id": self.id,
            "name": self.name,
            "nodes": [node.to_dict() for node in self.nodes],
            "connections": self.connections,
            "active": self.active,
            "settings": self.settings,
            "tags": self.tags,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat()
        }

    def export_json(self, output_path: str) -> None:
        """Export workflow to JSON file"""
        path = Path(output_path)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Workflow exported to {output_path}")


class WorkflowTemplate:
    """Pre-built workflow templates"""

    @staticmethod
    def create_webhook_trigger(name: str = "Webhook",
                               path: str = "webhook") -> N8NNode:
        """Create a webhook trigger node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.WEBHOOK,
            position=NodePosition(0, 0),
            parameters={
                "path": path,
                "httpMethod": "POST",
                "responseMode": "onReceived",
                "responseData": "firstEntryJson"
            }
        )

    @staticmethod
    def create_http_request(name: str, url: str, method: str = "GET") -> N8NNode:
        """Create HTTP request node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.HTTP_REQUEST,
            position=NodePosition(200, 0),
            parameters={
                "url": url,
                "method": method,
                "responseFormat": "json"
            }
        )

    @staticmethod
    def create_ai_router(name: str = "AI Model Router") -> N8NNode:
        """Create AI model routing node with switch logic"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.SWITCH,
            position=NodePosition(400, 0),
            parameters={
                "mode": "rules",
                "rules": {
                    "rules": [
                        {
                            "operation": "equals",
                            "value": "deepseek",
                            "output": 0
                        },
                        {
                            "operation": "equals",
                            "value": "gpt4",
                            "output": 1
                        },
                        {
                            "operation": "equals",
                            "value": "gemini",
                            "output": 2
                        }
                    ]
                },
                "fallbackOutput": 3
            }
        )

    @staticmethod
    def create_function_node(name: str, code: str) -> N8NNode:
        """Create JavaScript function node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.FUNCTION,
            position=NodePosition(600, 0),
            parameters={
                "functionCode": code
            }
        )

    @staticmethod
    def create_code_node(name: str, code: str, language: str = "python") -> N8NNode:
        """Create Python/JavaScript code node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.CODE,
            position=NodePosition(600, 0),
            parameters={
                "language": language,
                "code": code
            }
        )

    @staticmethod
    def create_email_node(name: str, to: str, subject: str) -> N8NNode:
        """Create email send node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.EMAIL,
            position=NodePosition(800, 0),
            parameters={
                "toEmail": to,
                "subject": subject,
                "text": "={{$json.body}}",
                "fromEmail": "noreply@automation.com"
            }
        )

    @staticmethod
    def create_database_node(name: str, operation: str = "insert",
                           table: str = "data") -> N8NNode:
        """Create database operation node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.DATABASE,
            position=NodePosition(800, 200),
            parameters={
                "operation": operation,
                "table": table,
                "columns": "={{Object.keys($json)}}"
            },
            credentials={
                "postgres": {
                    "id": "1",
                    "name": "Postgres account"
                }
            }
        )

    @staticmethod
    def create_schedule_trigger(name: str = "Schedule",
                                interval: int = 60) -> N8NNode:
        """Create scheduled trigger node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.SCHEDULE,
            position=NodePosition(0, 0),
            parameters={
                "rule": {
                    "interval": [
                        {
                            "field": "minutes",
                            "minutesInterval": interval
                        }
                    ]
                }
            }
        )

    @staticmethod
    def create_if_node(name: str, condition: str) -> N8NNode:
        """Create conditional IF node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.IF,
            position=NodePosition(400, 0),
            parameters={
                "conditions": {
                    "string": [
                        {
                            "value1": condition,
                            "operation": "notEmpty"
                        }
                    ]
                }
            }
        )

    @staticmethod
    def create_error_trigger(name: str = "Error Handler") -> N8NNode:
        """Create error trigger node"""
        return N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.ERROR_TRIGGER,
            position=NodePosition(0, 400),
            parameters={}
        )


class WorkflowChainer:
    """
    Advanced workflow chaining with conditional branching and error handling
    """

    def __init__(self, workflow: N8NWorkflow):
        self.workflow = workflow
        self.node_registry: Dict[str, N8NNode] = {}
        self.y_offset = 0

    def add_chain_step(self, node: N8NNode,
                      previous_node: Optional[str] = None,
                      condition: Optional[str] = None) -> str:
        """
        Add a step to the workflow chain

        Args:
            node: The node to add
            previous_node: Name of the previous node to connect from
            condition: Optional condition for branching

        Returns:
            The node name for further chaining
        """
        # Adjust position
        if previous_node and previous_node in self.node_registry:
            prev = self.node_registry[previous_node]
            node.position.x = prev.position.x + 200
            node.position.y = prev.position.y

        self.workflow.add_node(node)
        self.node_registry[node.name] = node

        if previous_node:
            self.workflow.connect_nodes(previous_node, node.name)

        return node.name

    def add_parallel_branch(self, nodes: List[N8NNode],
                           source_node: str) -> List[str]:
        """
        Add parallel branches from a source node

        Args:
            nodes: List of nodes to execute in parallel
            source_node: The node to branch from

        Returns:
            List of node names in the parallel branches
        """
        node_names = []

        for i, node in enumerate(nodes):
            # Offset vertically for parallel visualization
            node.position.y = self.node_registry[source_node].position.y + (i * 150)
            node.position.x = self.node_registry[source_node].position.x + 200

            self.workflow.add_node(node)
            self.workflow.connect_nodes(source_node, node.name, source_output=0)
            self.node_registry[node.name] = node
            node_names.append(node.name)

        return node_names

    def add_merge_point(self, name: str, source_nodes: List[str]) -> str:
        """
        Add a merge node to combine parallel branches

        Args:
            name: Name for the merge node
            source_nodes: List of nodes to merge

        Returns:
            The merge node name
        """
        if not source_nodes:
            raise ValueError("Must provide at least one source node")

        # Calculate average position
        avg_y = sum(self.node_registry[n].position.y for n in source_nodes) / len(source_nodes)
        avg_x = max(self.node_registry[n].position.x for n in source_nodes) + 200

        merge_node = N8NNode(
            id=str(uuid4()),
            name=name,
            type=NodeType.MERGE,
            position=NodePosition(avg_x, avg_y),
            parameters={
                "mode": "append"
            }
        )

        self.workflow.add_node(merge_node)
        self.node_registry[name] = merge_node

        # Connect all source nodes
        for source in source_nodes:
            self.workflow.connect_nodes(source, name)

        return name

    def add_error_handler(self, handler_workflow_id: str) -> str:
        """
        Add error handling to the workflow

        Args:
            handler_workflow_id: ID of workflow to execute on error

        Returns:
            The error handler node name
        """
        error_node = WorkflowTemplate.create_error_trigger()
        error_node.position.y = 400

        execute_node = N8NNode(
            id=str(uuid4()),
            name="Execute Error Workflow",
            type=NodeType.EXECUTE_WORKFLOW,
            position=NodePosition(200, 400),
            parameters={
                "workflowId": handler_workflow_id,
                "source": {
                    "mode": "workflowId",
                    "value": handler_workflow_id
                }
            }
        )

        self.workflow.add_node(error_node)
        self.workflow.add_node(execute_node)
        self.workflow.connect_nodes(error_node.name, execute_node.name)

        self.node_registry[error_node.name] = error_node
        self.node_registry[execute_node.name] = execute_node

        return error_node.name


class N8NWorkflowManager:
    """
    Main manager for creating and managing n8n workflows
    """

    def __init__(self, output_dir: str = "n8n_workflows"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.workflows: Dict[str, N8NWorkflow] = {}

    def create_workflow(self, name: str, tags: Optional[List[str]] = None) -> N8NWorkflow:
        """Create a new workflow"""
        workflow = N8NWorkflow(
            id=str(uuid4()),
            name=name,
            tags=tags or []
        )
        self.workflows[name] = workflow
        logger.info(f"Created workflow: {name}")
        return workflow

    def create_data_ingestion_workflow(self, name: str,
                                       source_url: str,
                                       db_table: str) -> N8NWorkflow:
        """
        Create a data ingestion workflow template

        Flow: Schedule -> HTTP Request -> Transform -> Database
        """
        workflow = self.create_workflow(name, tags=["data-ingestion"])
        chainer = WorkflowChainer(workflow)

        # Schedule trigger
        schedule = WorkflowTemplate.create_schedule_trigger("Every Hour", interval=60)
        chainer.add_chain_step(schedule)

        # HTTP request to fetch data
        http = WorkflowTemplate.create_http_request("Fetch Data", source_url, "GET")
        chainer.add_chain_step(http, schedule.name)

        # Transform data
        transform_code = """
// Transform incoming data
const items = $input.all();
return items.map(item => ({
  json: {
    ...item.json,
    ingested_at: new Date().toISOString(),
    source: 'api'
  }
}));
"""
        transform = WorkflowTemplate.create_function_node("Transform", transform_code)
        chainer.add_chain_step(transform, http.name)

        # Save to database
        db = WorkflowTemplate.create_database_node("Save to DB", "insert", db_table)
        chainer.add_chain_step(db, transform.name)

        return workflow

    def create_ai_routing_workflow(self, name: str) -> N8NWorkflow:
        """
        Create AI model routing workflow

        Flow: Webhook -> Route to AI Model -> Process Response -> Store
        """
        workflow = self.create_workflow(name, tags=["ai", "routing"])
        chainer = WorkflowChainer(workflow)

        # Webhook trigger
        webhook = WorkflowTemplate.create_webhook_trigger("AI Request", "ai-request")
        chainer.add_chain_step(webhook)

        # AI router
        router = WorkflowTemplate.create_ai_router("Route to Model")
        chainer.add_chain_step(router, webhook.name)

        # Create parallel branches for different models
        deepseek = WorkflowTemplate.create_http_request(
            "DeepSeek API",
            "https://api.deepseek.com/v1/chat",
            "POST"
        )
        gpt4 = WorkflowTemplate.create_http_request(
            "GPT-4 API",
            "https://api.openai.com/v1/chat/completions",
            "POST"
        )
        gemini = WorkflowTemplate.create_http_request(
            "Gemini API",
            "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
            "POST"
        )

        branches = chainer.add_parallel_branch([deepseek, gpt4, gemini], router.name)

        # Merge responses
        merge = chainer.add_merge_point("Merge Responses", branches)

        # Store results
        db = WorkflowTemplate.create_database_node("Store Results", "insert", "ai_responses")
        chainer.add_chain_step(db, merge)

        return workflow

    def create_webhook_email_workflow(self, name: str,
                                      email_to: str) -> N8NWorkflow:
        """
        Create webhook to email workflow

        Flow: Webhook -> Process -> Email
        """
        workflow = self.create_workflow(name, tags=["webhook", "email"])
        chainer = WorkflowChainer(workflow)

        # Webhook
        webhook = WorkflowTemplate.create_webhook_trigger("Incoming Alert", "alert")
        chainer.add_chain_step(webhook)

        # Process
        process_code = """
const data = $input.first().json;
return {
  json: {
    body: `Alert received at ${new Date().toISOString()}\\n\\n${JSON.stringify(data, null, 2)}`,
    priority: data.priority || 'normal',
    timestamp: new Date().toISOString()
  }
};
"""
        process = WorkflowTemplate.create_function_node("Process Alert", process_code)
        chainer.add_chain_step(process, webhook.name)

        # Email
        email = WorkflowTemplate.create_email_node(
            "Send Email",
            email_to,
            "Alert: {{$json.priority}}"
        )
        chainer.add_chain_step(email, process.name)

        return workflow

    def create_database_sync_workflow(self, name: str) -> N8NWorkflow:
        """
        Create database synchronization workflow

        Flow: Schedule -> Query Source DB -> Transform -> Update Target DB
        """
        workflow = self.create_workflow(name, tags=["database", "sync"])
        chainer = WorkflowChainer(workflow)

        # Schedule
        schedule = WorkflowTemplate.create_schedule_trigger("Every 5 Minutes", interval=5)
        chainer.add_chain_step(schedule)

        # Query source
        source_db = WorkflowTemplate.create_database_node("Query Source", "select", "source_table")
        chainer.add_chain_step(source_db, schedule.name)

        # Transform
        transform_code = """
const items = $input.all();
return items.map(item => ({
  json: {
    ...item.json,
    synced_at: new Date().toISOString(),
    sync_source: 'source_db'
  }
}));
"""
        transform = WorkflowTemplate.create_function_node("Transform Data", transform_code)
        chainer.add_chain_step(transform, source_db.name)

        # Update target
        target_db = WorkflowTemplate.create_database_node("Update Target", "insert", "target_table")
        chainer.add_chain_step(target_db, transform.name)

        return workflow

    def export_workflow(self, name: str, filename: Optional[str] = None) -> str:
        """Export a workflow to JSON file"""
        if name not in self.workflows:
            raise ValueError(f"Workflow '{name}' not found")

        workflow = self.workflows[name]
        output_file = filename or f"{name.lower().replace(' ', '_')}.json"
        output_path = self.output_dir / output_file

        workflow.export_json(str(output_path))
        return str(output_path)

    def export_all_workflows(self) -> List[str]:
        """Export all workflows"""
        exported = []
        for name in self.workflows:
            path = self.export_workflow(name)
            exported.append(path)
        return exported

    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get summary of all workflows"""
        return {
            "total_workflows": len(self.workflows),
            "workflows": [
                {
                    "name": w.name,
                    "id": w.id,
                    "nodes": len(w.nodes),
                    "connections": len(w.connections),
                    "tags": w.tags,
                    "active": w.active
                }
                for w in self.workflows.values()
            ]
        }


# Example usage
def main():
    """Example usage of N8NWorkflowManager"""
    manager = N8NWorkflowManager()

    # Create data ingestion workflow
    manager.create_data_ingestion_workflow(
        "Market Data Ingestion",
        "https://api.coingecko.com/api/v3/coins/markets",
        "market_data"
    )

    # Create AI routing workflow
    manager.create_ai_routing_workflow("Multi-Model AI Router")

    # Create webhook email workflow
    manager.create_webhook_email_workflow(
        "Alert to Email",
        "admin@example.com"
    )

    # Create database sync workflow
    manager.create_database_sync_workflow("DB Sync")

    # Export all workflows
    exported = manager.export_all_workflows()
    print(f"\nExported {len(exported)} workflows:")
    for path in exported:
        print(f"  - {path}")

    # Print summary
    summary = manager.get_workflow_summary()
    print(f"\nWorkflow Summary:\n{json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
