"""
N8N Workflow Router - Generate and manage n8n-compatible workflow JSON
Supports data ingestion, AI model routing, webhooks, email, database sync, and conditional branching.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NodeType(Enum):
    """N8N node types"""
    WEBHOOK = "n8n-nodes-base.webhook"
    HTTP_REQUEST = "n8n-nodes-base.httpRequest"
    CODE = "n8n-nodes-base.code"
    IF = "n8n-nodes-base.if"
    SWITCH = "n8n-nodes-base.switch"
    SET = "n8n-nodes-base.set"
    EMAIL = "n8n-nodes-base.emailSend"
    DATABASE = "n8n-nodes-base.postgres"
    SCHEDULE = "n8n-nodes-base.scheduleTrigger"
    FUNCTION = "n8n-nodes-base.function"
    MERGE = "n8n-nodes-base.merge"
    SPLIT = "n8n-nodes-base.splitInBatches"
    AI_AGENT = "n8n-nodes-base.agent"
    OPENAI = "n8n-nodes-base.openAi"


class TriggerType(Enum):
    """Workflow trigger types"""
    WEBHOOK = "webhook"
    SCHEDULE = "schedule"
    MANUAL = "manual"
    EMAIL = "email"


@dataclass
class N8NNode:
    """N8N workflow node"""
    name: str
    type: NodeType
    position: List[int]
    parameters: Dict[str, Any] = field(default_factory=dict)
    credentials: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to n8n node format"""
        node_data = {
            "name": self.name,
            "type": self.type.value,
            "typeVersion": 1,
            "position": self.position,
            "parameters": self.parameters
        }
        
        if self.credentials:
            node_data["credentials"] = self.credentials
            
        return node_data


@dataclass
class N8NConnection:
    """N8N node connection"""
    source_node: str
    target_node: str
    source_output: int = 0
    target_input: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to n8n connection format"""
        return {
            "node": self.target_node,
            "type": "main",
            "index": self.target_input
        }


@dataclass
class N8NWorkflow:
    """Complete N8N workflow"""
    name: str
    nodes: List[N8NNode] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)
    active: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)
    
    def add_node(self, node: N8NNode) -> None:
        """Add node to workflow"""
        self.nodes.append(node)
        logger.info(f"Added node: {node.name} ({node.type.value})")
        
    def connect_nodes(self, connection: N8NConnection) -> None:
        """Connect two nodes"""
        if connection.source_node not in self.connections:
            self.connections[connection.source_node] = {"main": [[]]}
            
        # Ensure output index exists
        while len(self.connections[connection.source_node]["main"]) <= connection.source_output:
            self.connections[connection.source_node]["main"].append([])
            
        self.connections[connection.source_node]["main"][connection.source_output].append(
            connection.to_dict()
        )
        logger.info(f"Connected {connection.source_node} -> {connection.target_node}")
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to n8n workflow JSON format"""
        return {
            "name": self.name,
            "nodes": [node.to_dict() for node in self.nodes],
            "connections": self.connections,
            "active": self.active,
            "settings": self.settings,
            "id": str(uuid.uuid4()),
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }
        
    def export_json(self, filepath: str) -> None:
        """Export workflow to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Workflow exported to {filepath}")


class WorkflowTemplate:
    """Pre-built workflow templates"""
    
    @staticmethod
    def data_ingestion_pipeline() -> N8NWorkflow:
        """Create data ingestion workflow"""
        workflow = N8NWorkflow(name="Data Ingestion Pipeline")
        
        # Webhook trigger
        webhook = N8NNode(
            name="Webhook",
            type=NodeType.WEBHOOK,
            position=[250, 300],
            parameters={
                "path": "data-ingest",
                "responseMode": "onReceived",
                "httpMethod": "POST"
            }
        )
        workflow.add_node(webhook)
        
        # Data validation
        validate = N8NNode(
            name="Validate Data",
            type=NodeType.CODE,
            position=[450, 300],
            parameters={
                "jsCode": """
// Validate incoming data
const data = items[0].json;

if (!data.source || !data.payload) {
  throw new Error('Missing required fields');
}

return items.map(item => ({
  json: {
    ...item.json,
    validated: true,
    timestamp: new Date().toISOString()
  }
}));
"""
            }
        )
        workflow.add_node(validate)
        workflow.connect_nodes(N8NConnection("Webhook", "Validate Data"))
        
        # Store in database
        db_store = N8NNode(
            name="Store in Database",
            type=NodeType.DATABASE,
            position=[650, 300],
            parameters={
                "operation": "insert",
                "table": "ingested_data",
                "columns": "source,payload,timestamp"
            },
            credentials={"postgres": "postgres_credentials"}
        )
        workflow.add_node(db_store)
        workflow.connect_nodes(N8NConnection("Validate Data", "Store in Database"))
        
        return workflow
        
    @staticmethod
    def ai_model_router() -> N8NWorkflow:
        """Create AI model routing workflow"""
        workflow = N8NWorkflow(name="AI Model Router")
        
        # Schedule trigger
        schedule = N8NNode(
            name="Schedule Trigger",
            type=NodeType.SCHEDULE,
            position=[250, 300],
            parameters={
                "rule": {
                    "interval": [{"field": "minutes", "minutesInterval": 15}]
                }
            }
        )
        workflow.add_node(schedule)
        
        # Fetch pending tasks
        fetch_tasks = N8NNode(
            name="Fetch Tasks",
            type=NodeType.HTTP_REQUEST,
            position=[450, 300],
            parameters={
                "url": "http://localhost:8000/api/tasks/pending",
                "method": "GET",
                "responseFormat": "json"
            }
        )
        workflow.add_node(fetch_tasks)
        workflow.connect_nodes(N8NConnection("Schedule Trigger", "Fetch Tasks"))
        
        # Route to appropriate AI model
        router = N8NNode(
            name="Route to AI Model",
            type=NodeType.SWITCH,
            position=[650, 300],
            parameters={
                "mode": "expression",
                "rules": {
                    "rules": [
                        {
                            "output": 0,
                            "conditions": {
                                "conditions": [{
                                    "leftValue": "={{ $json.model }}",
                                    "rightValue": "deepseek",
                                    "operator": "equal"
                                }]
                            }
                        },
                        {
                            "output": 1,
                            "conditions": {
                                "conditions": [{
                                    "leftValue": "={{ $json.model }}",
                                    "rightValue": "gpt4",
                                    "operator": "equal"
                                }]
                            }
                        }
                    ]
                }
            }
        )
        workflow.add_node(router)
        workflow.connect_nodes(N8NConnection("Fetch Tasks", "Route to AI Model"))
        
        # DeepSeek endpoint
        deepseek = N8NNode(
            name="DeepSeek API",
            type=NodeType.HTTP_REQUEST,
            position=[850, 200],
            parameters={
                "url": "https://api.deepseek.com/v1/chat/completions",
                "method": "POST",
                "sendBody": True,
                "bodyParameters": {
                    "parameters": [
                        {"name": "model", "value": "deepseek-chat"},
                        {"name": "messages", "value": "={{ $json.messages }}"}
                    ]
                }
            }
        )
        workflow.add_node(deepseek)
        workflow.connect_nodes(N8NConnection("Route to AI Model", "DeepSeek API", source_output=0))
        
        # GPT-4 endpoint
        gpt4 = N8NNode(
            name="GPT-4 API",
            type=NodeType.OPENAI,
            position=[850, 400],
            parameters={
                "model": "gpt-4",
                "messages": "={{ $json.messages }}"
            },
            credentials={"openAiApi": "openai_credentials"}
        )
        workflow.add_node(gpt4)
        workflow.connect_nodes(N8NConnection("Route to AI Model", "GPT-4 API", source_output=1))
        
        return workflow
        
    @staticmethod
    def webhook_email_notification() -> N8NWorkflow:
        """Create webhook to email notification workflow"""
        workflow = N8NWorkflow(name="Webhook Email Notification")
        
        # Webhook trigger
        webhook = N8NNode(
            name="Webhook Trigger",
            type=NodeType.WEBHOOK,
            position=[250, 300],
            parameters={
                "path": "notify",
                "httpMethod": "POST"
            }
        )
        workflow.add_node(webhook)
        
        # Check priority
        check_priority = N8NNode(
            name="Check Priority",
            type=NodeType.IF,
            position=[450, 300],
            parameters={
                "conditions": {
                    "string": [{
                        "value1": "={{ $json.priority }}",
                        "value2": "high",
                        "operation": "equals"
                    }]
                }
            }
        )
        workflow.add_node(check_priority)
        workflow.connect_nodes(N8NConnection("Webhook Trigger", "Check Priority"))
        
        # Send urgent email
        urgent_email = N8NNode(
            name="Send Urgent Email",
            type=NodeType.EMAIL,
            position=[650, 200],
            parameters={
                "fromEmail": "alerts@agenticseek.com",
                "toEmail": "={{ $json.recipient }}",
                "subject": "[URGENT] {{ $json.subject }}",
                "text": "={{ $json.message }}"
            },
            credentials={"smtp": "smtp_credentials"}
        )
        workflow.add_node(urgent_email)
        workflow.connect_nodes(N8NConnection("Check Priority", "Send Urgent Email", source_output=0))
        
        # Send normal email
        normal_email = N8NNode(
            name="Send Normal Email",
            type=NodeType.EMAIL,
            position=[650, 400],
            parameters={
                "fromEmail": "notifications@agenticseek.com",
                "toEmail": "={{ $json.recipient }}",
                "subject": "={{ $json.subject }}",
                "text": "={{ $json.message }}"
            },
            credentials={"smtp": "smtp_credentials"}
        )
        workflow.add_node(normal_email)
        workflow.connect_nodes(N8NConnection("Check Priority", "Send Normal Email", source_output=1))
        
        return workflow
        
    @staticmethod
    def database_sync_pipeline() -> N8NWorkflow:
        """Create database synchronization workflow"""
        workflow = N8NWorkflow(name="Database Sync Pipeline")
        
        # Schedule trigger (every hour)
        schedule = N8NNode(
            name="Hourly Sync",
            type=NodeType.SCHEDULE,
            position=[250, 300],
            parameters={
                "rule": {
                    "interval": [{"field": "hours", "hoursInterval": 1}]
                }
            }
        )
        workflow.add_node(schedule)
        
        # Fetch from source DB
        fetch_source = N8NNode(
            name="Fetch Source Data",
            type=NodeType.DATABASE,
            position=[450, 300],
            parameters={
                "operation": "executeQuery",
                "query": "SELECT * FROM source_table WHERE updated_at > NOW() - INTERVAL '1 hour'"
            },
            credentials={"postgres": "source_db_credentials"}
        )
        workflow.add_node(fetch_source)
        workflow.connect_nodes(N8NConnection("Hourly Sync", "Fetch Source Data"))
        
        # Transform data
        transform = N8NNode(
            name="Transform Data",
            type=NodeType.CODE,
            position=[650, 300],
            parameters={
                "jsCode": """
// Transform data for target database
return items.map(item => ({
  json: {
    id: item.json.id,
    data: JSON.stringify(item.json),
    synced_at: new Date().toISOString()
  }
}));
"""
            }
        )
        workflow.add_node(transform)
        workflow.connect_nodes(N8NConnection("Fetch Source Data", "Transform Data"))
        
        # Upsert to target DB
        upsert_target = N8NNode(
            name="Upsert Target Data",
            type=NodeType.DATABASE,
            position=[850, 300],
            parameters={
                "operation": "insert",
                "table": "target_table",
                "columns": "id,data,synced_at",
                "onConflict": "id",
                "onConflictAction": "update"
            },
            credentials={"postgres": "target_db_credentials"}
        )
        workflow.add_node(upsert_target)
        workflow.connect_nodes(N8NConnection("Transform Data", "Upsert Target Data"))
        
        return workflow


class WorkflowChainer:
    """Chain multiple workflows with conditional branching and error handling"""
    
    def __init__(self):
        self.workflows: List[N8NWorkflow] = []
        self.error_handlers: Dict[str, Callable] = {}
        
    def add_workflow(self, workflow: N8NWorkflow) -> None:
        """Add workflow to chain"""
        self.workflows.append(workflow)
        logger.info(f"Added workflow to chain: {workflow.name}")
        
    def add_error_handler(self, workflow_name: str, handler: Callable) -> None:
        """Add error handler for specific workflow"""
        self.error_handlers[workflow_name] = handler
        
    def create_master_workflow(self, name: str = "Master Workflow Chain") -> N8NWorkflow:
        """Create a master workflow that chains all sub-workflows"""
        master = N8NWorkflow(name=name)
        
        # Start trigger
        start = N8NNode(
            name="Start",
            type=NodeType.WEBHOOK,
            position=[250, 300],
            parameters={
                "path": "master-chain",
                "httpMethod": "POST"
            }
        )
        master.add_node(start)
        
        prev_node = "Start"
        y_position = 300
        
        for i, workflow in enumerate(self.workflows):
            x_position = 450 + (i * 300)
            
            # Execute sub-workflow
            execute_node = N8NNode(
                name=f"Execute {workflow.name}",
                type=NodeType.HTTP_REQUEST,
                position=[x_position, y_position],
                parameters={
                    "url": f"http://localhost:5678/webhook/{workflow.name.lower().replace(' ', '-')}",
                    "method": "POST",
                    "sendBody": True,
                    "jsonParameters": True,
                    "bodyParametersJson": "={{ $json }}"
                }
            )
            master.add_node(execute_node)
            master.connect_nodes(N8NConnection(prev_node, execute_node.name))
            
            # Error handling
            error_check = N8NNode(
                name=f"Check {workflow.name} Status",
                type=NodeType.IF,
                position=[x_position, y_position + 150],
                parameters={
                    "conditions": {
                        "number": [{
                            "value1": "={{ $json.statusCode }}",
                            "value2": 200,
                            "operation": "equal"
                        }]
                    }
                }
            )
            master.add_node(error_check)
            master.connect_nodes(N8NConnection(execute_node.name, error_check.name))
            
            prev_node = error_check.name
            
        return master
        
    def export_all(self, output_dir: str = "n8n_workflows") -> None:
        """Export all workflows to JSON files"""
        Path(output_dir).mkdir(exist_ok=True)
        
        for workflow in self.workflows:
            filename = f"{workflow.name.lower().replace(' ', '_')}.json"
            filepath = Path(output_dir) / filename
            workflow.export_json(str(filepath))
            
        logger.info(f"Exported {len(self.workflows)} workflows to {output_dir}")


class N8NWorkflowManager:
    """Main manager for N8N workflow generation and management"""
    
    def __init__(self):
        self.workflows: Dict[str, N8NWorkflow] = {}
        self.chainer = WorkflowChainer()
        
    def create_from_template(self, template_name: str) -> N8NWorkflow:
        """Create workflow from template"""
        templates = {
            "data_ingestion": WorkflowTemplate.data_ingestion_pipeline,
            "ai_router": WorkflowTemplate.ai_model_router,
            "webhook_email": WorkflowTemplate.webhook_email_notification,
            "db_sync": WorkflowTemplate.database_sync_pipeline
        }
        
        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")
            
        workflow = templates[template_name]()
        self.workflows[workflow.name] = workflow
        logger.info(f"Created workflow from template: {template_name}")
        
        return workflow
        
    def create_custom_workflow(self, name: str) -> N8NWorkflow:
        """Create custom workflow"""
        workflow = N8NWorkflow(name=name)
        self.workflows[name] = workflow
        return workflow
        
    def add_conditional_branch(self, 
                              workflow: N8NWorkflow,
                              condition_node_name: str,
                              condition: str,
                              true_branch: List[N8NNode],
                              false_branch: List[N8NNode]) -> None:
        """Add conditional branching to workflow"""
        # Create IF node
        if_node = N8NNode(
            name=condition_node_name,
            type=NodeType.IF,
            position=[500, 300],
            parameters={
                "conditions": {
                    "string": [{
                        "value1": condition,
                        "operation": "notEmpty"
                    }]
                }
            }
        )
        workflow.add_node(if_node)
        
        # Add true branch nodes
        for i, node in enumerate(true_branch):
            node.position = [700, 200 + (i * 100)]
            workflow.add_node(node)
            if i == 0:
                workflow.connect_nodes(N8NConnection(condition_node_name, node.name, source_output=0))
            else:
                workflow.connect_nodes(N8NConnection(true_branch[i-1].name, node.name))
                
        # Add false branch nodes
        for i, node in enumerate(false_branch):
            node.position = [700, 400 + (i * 100)]
            workflow.add_node(node)
            if i == 0:
                workflow.connect_nodes(N8NConnection(condition_node_name, node.name, source_output=1))
            else:
                workflow.connect_nodes(N8NConnection(false_branch[i-1].name, node.name))
                
    def export_workflow(self, workflow_name: str, filepath: str) -> None:
        """Export specific workflow"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow not found: {workflow_name}")
            
        self.workflows[workflow_name].export_json(filepath)
        
    def export_all_workflows(self, output_dir: str = "n8n_workflows") -> None:
        """Export all workflows"""
        Path(output_dir).mkdir(exist_ok=True)
        
        for name, workflow in self.workflows.items():
            filename = f"{name.lower().replace(' ', '_')}.json"
            filepath = Path(output_dir) / filename
            workflow.export_json(str(filepath))
            
        logger.info(f"Exported {len(self.workflows)} workflows to {output_dir}")
        
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get summary of all workflows"""
        return {
            "total_workflows": len(self.workflows),
            "workflows": [
                {
                    "name": name,
                    "nodes": len(workflow.nodes),
                    "connections": sum(len(conns["main"][0]) for conns in workflow.connections.values()),
                    "active": workflow.active
                }
                for name, workflow in self.workflows.items()
            ]
        }


def main():
    """Example usage of N8N Workflow Manager"""
    
    # Initialize manager
    manager = N8NWorkflowManager()
    
    # Create workflows from templates
    manager.create_from_template("data_ingestion")
    manager.create_from_template("ai_router")
    manager.create_from_template("webhook_email")
    manager.create_from_template("db_sync")
    
    # Create custom workflow
    custom = manager.create_custom_workflow("Custom Intelligence Pipeline")
    
    # Add webhook trigger
    webhook = N8NNode(
        name="Intelligence Webhook",
        type=NodeType.WEBHOOK,
        position=[250, 300],
        parameters={"path": "intelligence", "httpMethod": "POST"}
    )
    custom.add_node(webhook)
    
    # Add processing node
    process = N8NNode(
        name="Process Intelligence",
        type=NodeType.CODE,
        position=[450, 300],
        parameters={
            "jsCode": "return items.map(item => ({json: {...item.json, processed: true}}));"
        }
    )
    custom.add_node(process)
    custom.connect_nodes(N8NConnection("Intelligence Webhook", "Process Intelligence"))
    
    # Export all workflows
    manager.export_all_workflows()
    
    # Print summary
    summary = manager.get_workflow_summary()
    print("\n" + "="*60)
    print("N8N WORKFLOW MANAGER - SUMMARY")
    print("="*60)
    print(f"Total Workflows: {summary['total_workflows']}")
    print("\nWorkflows:")
    for wf in summary['workflows']:
        print(f"  • {wf['name']}: {wf['nodes']} nodes, {wf['connections']} connections")
    print("="*60)


if __name__ == "__main__":
    main()
