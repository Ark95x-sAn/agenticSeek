"""
Active Income Optimizer - Freelance Task Router, Client Acquisition, Pricing Engine
Implements lead scoring, dynamic pricing, and project pipeline management.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import random
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(Enum):
    """Task status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ClientTier(Enum):
    """Client tier classification"""
    ENTERPRISE = "enterprise"
    PREMIUM = "premium"
    STANDARD = "standard"
    STARTER = "starter"


class ProjectPhase(Enum):
    """Project lifecycle phases"""
    DISCOVERY = "discovery"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    ACTIVE = "active"
    DELIVERY = "delivery"
    CLOSED = "closed"


@dataclass
class FreelanceTask:
    """Freelance task/gig"""
    task_id: str
    title: str
    description: str
    client: str
    priority: TaskPriority
    status: TaskStatus
    estimated_hours: float
    hourly_rate: float
    deadline: datetime
    skills_required: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def calculate_value(self) -> float:
        """Calculate task monetary value"""
        return self.estimated_hours * self.hourly_rate
        
    def is_overdue(self) -> bool:
        """Check if task is overdue"""
        return datetime.now() > self.deadline and self.status != TaskStatus.COMPLETED


@dataclass
class Lead:
    """Client lead"""
    lead_id: str
    name: str
    email: str
    company: str
    project_description: str
    budget_range: Tuple[float, float]
    source: str  # referral, linkedin, upwork, etc.
    score: float = 0.0
    tier: Optional[ClientTier] = None
    contacted_at: Optional[datetime] = None
    converted: bool = False
    
    def calculate_score(self) -> float:
        """Calculate lead quality score"""
        score = 0.0
        
        # Budget score (0-40 points)
        avg_budget = (self.budget_range[0] + self.budget_range[1]) / 2
        if avg_budget > 10000:
            score += 40
        elif avg_budget > 5000:
            score += 30
        elif avg_budget > 2000:
            score += 20
        else:
            score += 10
            
        # Source score (0-30 points)
        source_scores = {
            "referral": 30,
            "linkedin": 25,
            "upwork": 20,
            "cold_outreach": 10
        }
        score += source_scores.get(self.source, 15)
        
        # Company presence (0-30 points)
        if self.company and len(self.company) > 3:
            score += 30
        else:
            score += 10
            
        self.score = score
        return score


@dataclass
class Client:
    """Active client"""
    client_id: str
    name: str
    email: str
    company: str
    tier: ClientTier
    lifetime_value: float = 0.0
    projects_completed: int = 0
    satisfaction_score: float = 0.0
    onboarded_at: datetime = field(default_factory=datetime.now)
    
    def update_tier(self) -> None:
        """Update client tier based on lifetime value"""
        if self.lifetime_value > 50000:
            self.tier = ClientTier.ENTERPRISE
        elif self.lifetime_value > 20000:
            self.tier = ClientTier.PREMIUM
        elif self.lifetime_value > 5000:
            self.tier = ClientTier.STANDARD
        else:
            self.tier = ClientTier.STARTER


@dataclass
class Project:
    """Client project"""
    project_id: str
    client_id: str
    title: str
    description: str
    phase: ProjectPhase
    total_value: float
    hours_allocated: float
    hours_used: float = 0.0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    deliverables: List[str] = field(default_factory=list)
    
    def get_progress(self) -> float:
        """Calculate project progress percentage"""
        return (self.hours_used / self.hours_allocated * 100) if self.hours_allocated > 0 else 0.0
        
    def get_remaining_budget(self) -> float:
        """Calculate remaining budget"""
        hourly_rate = self.total_value / self.hours_allocated if self.hours_allocated > 0 else 0
        return (self.hours_allocated - self.hours_used) * hourly_rate


class FreelanceTaskRouter:
    """Route and prioritize freelance tasks"""
    
    def __init__(self):
        self.tasks: Dict[str, FreelanceTask] = {}
        self.task_queue: List[str] = []
        
    def add_task(self, task: FreelanceTask) -> None:
        """Add task to router"""
        self.tasks[task.task_id] = task
        self._update_queue()
        logger.info(f"Added task: {task.title} (${task.calculate_value():.2f})")
        
    def _update_queue(self) -> None:
        """Update task queue based on priority and deadline"""
        # Sort by priority and deadline
        priority_weights = {
            TaskPriority.CRITICAL: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 1
        }
        
        pending_tasks = [
            (task_id, task) for task_id, task in self.tasks.items()
            if task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
        ]
        
        # Sort by priority weight and deadline
        sorted_tasks = sorted(
            pending_tasks,
            key=lambda x: (
                -priority_weights[x[1].priority],
                x[1].deadline
            )
        )
        
        self.task_queue = [task_id for task_id, _ in sorted_tasks]
        
    def get_next_task(self) -> Optional[FreelanceTask]:
        """Get next task to work on"""
        if not self.task_queue:
            return None
        return self.tasks.get(self.task_queue[0])
        
    def complete_task(self, task_id: str) -> None:
        """Mark task as completed"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].completed_at = datetime.now()
            self._update_queue()
            logger.info(f"Completed task: {self.tasks[task_id].title}")
            
    def get_overdue_tasks(self) -> List[FreelanceTask]:
        """Get all overdue tasks"""
        return [task for task in self.tasks.values() if task.is_overdue()]
        
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task statistics"""
        total_value = sum(task.calculate_value() for task in self.tasks.values())
        completed_value = sum(
            task.calculate_value() for task in self.tasks.values()
            if task.status == TaskStatus.COMPLETED
        )
        
        return {
            "total_tasks": len(self.tasks),
            "pending": sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING),
            "in_progress": sum(1 for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS),
            "completed": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
            "overdue": len(self.get_overdue_tasks()),
            "total_value": total_value,
            "completed_value": completed_value
        }


class ClientAcquisitionPipeline:
    """Manage client acquisition with lead scoring"""
    
    def __init__(self):
        self.leads: Dict[str, Lead] = {}
        self.clients: Dict[str, Client] = {}
        
    def add_lead(self, lead: Lead) -> None:
        """Add new lead to pipeline"""
        lead.calculate_score()
        
        # Auto-assign tier based on score
        if lead.score >= 80:
            lead.tier = ClientTier.ENTERPRISE
        elif lead.score >= 60:
            lead.tier = ClientTier.PREMIUM
        elif lead.score >= 40:
            lead.tier = ClientTier.STANDARD
        else:
            lead.tier = ClientTier.STARTER
            
        self.leads[lead.lead_id] = lead
        logger.info(f"Added lead: {lead.name} (Score: {lead.score:.1f}, Tier: {lead.tier.value})")
        
    def get_hot_leads(self, min_score: float = 70.0) -> List[Lead]:
        """Get high-quality leads"""
        return sorted(
            [lead for lead in self.leads.values() if lead.score >= min_score and not lead.converted],
            key=lambda x: x.score,
            reverse=True
        )
        
    def convert_lead(self, lead_id: str) -> Optional[Client]:
        """Convert lead to client"""
        if lead_id not in self.leads:
            return None
            
        lead = self.leads[lead_id]
        lead.converted = True
        
        client = Client(
            client_id=f"CLIENT_{len(self.clients) + 1}",
            name=lead.name,
            email=lead.email,
            company=lead.company,
            tier=lead.tier or ClientTier.STARTER
        )
        
        self.clients[client.client_id] = client
        logger.info(f"Converted lead to client: {client.name}")
        
        return client
        
    def update_client_value(self, client_id: str, project_value: float) -> None:
        """Update client lifetime value"""
        if client_id in self.clients:
            client = self.clients[client_id]
            client.lifetime_value += project_value
            client.projects_completed += 1
            client.update_tier()
            logger.info(f"Updated client value: {client.name} - ${client.lifetime_value:.2f}")
            
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            "total_leads": len(self.leads),
            "hot_leads": len(self.get_hot_leads()),
            "converted_leads": sum(1 for l in self.leads.values() if l.converted),
            "total_clients": len(self.clients),
            "conversion_rate": (sum(1 for l in self.leads.values() if l.converted) / len(self.leads) * 100)
                              if self.leads else 0.0,
            "total_client_value": sum(c.lifetime_value for c in self.clients.values())
        }


class PricingEngine:
    """Dynamic pricing engine with rate optimization"""
    
    def __init__(self, base_hourly_rate: float = 100.0):
        self.base_hourly_rate = base_hourly_rate
        self.rate_history: List[Dict[str, Any]] = []
        
    def calculate_rate(self,
                      client_tier: ClientTier,
                      project_complexity: float,  # 0.0 to 1.0
                      urgency: float,  # 0.0 to 1.0
                      skills_premium: float = 0.0) -> float:
        """Calculate dynamic hourly rate"""
        
        # Base rate
        rate = self.base_hourly_rate
        
        # Client tier multiplier
        tier_multipliers = {
            ClientTier.ENTERPRISE: 1.5,
            ClientTier.PREMIUM: 1.3,
            ClientTier.STANDARD: 1.1,
            ClientTier.STARTER: 1.0
        }
        rate *= tier_multipliers[client_tier]
        
        # Complexity multiplier (0% to 50% increase)
        rate *= (1.0 + (project_complexity * 0.5))
        
        # Urgency multiplier (0% to 30% increase)
        rate *= (1.0 + (urgency * 0.3))
        
        # Skills premium
        rate += skills_premium
        
        # Record rate
        self.rate_history.append({
            "rate": rate,
            "client_tier": client_tier.value,
            "complexity": project_complexity,
            "urgency": urgency,
            "timestamp": datetime.now().isoformat()
        })
        
        return round(rate, 2)
        
    def calculate_project_price(self,
                               estimated_hours: float,
                               client_tier: ClientTier,
                               complexity: float,
                               urgency: float,
                               discount: float = 0.0) -> Dict[str, Any]:
        """Calculate total project price"""
        
        hourly_rate = self.calculate_rate(client_tier, complexity, urgency)
        subtotal = estimated_hours * hourly_rate
        discount_amount = subtotal * discount
        total = subtotal - discount_amount
        
        return {
            "hourly_rate": hourly_rate,
            "estimated_hours": estimated_hours,
            "subtotal": subtotal,
            "discount": discount_amount,
            "total": total,
            "breakdown": {
                "base_rate": self.base_hourly_rate,
                "tier_adjusted": hourly_rate,
                "hours": estimated_hours
            }
        }
        
    def optimize_base_rate(self) -> float:
        """Optimize base rate based on market demand"""
        if len(self.rate_history) < 10:
            return self.base_hourly_rate
            
        # Calculate average accepted rate
        recent_rates = [r['rate'] for r in self.rate_history[-20:]]
        avg_rate = sum(recent_rates) / len(recent_rates)
        
        # Adjust base rate (conservative 5% adjustment)
        if avg_rate > self.base_hourly_rate * 1.2:
            self.base_hourly_rate *= 1.05
            logger.info(f"Increased base rate to ${self.base_hourly_rate:.2f}")
        elif avg_rate < self.base_hourly_rate * 0.9:
            self.base_hourly_rate *= 0.95
            logger.info(f"Decreased base rate to ${self.base_hourly_rate:.2f}")
            
        return self.base_hourly_rate


class ProjectPipeline:
    """Manage project pipeline and lifecycle"""
    
    def __init__(self):
        self.projects: Dict[str, Project] = {}
        
    def create_project(self, project: Project) -> None:
        """Add project to pipeline"""
        self.projects[project.project_id] = project
        logger.info(f"Created project: {project.title} (${project.total_value:.2f})")
        
    def update_phase(self, project_id: str, new_phase: ProjectPhase) -> None:
        """Update project phase"""
        if project_id in self.projects:
            self.projects[project_id].phase = new_phase
            logger.info(f"Updated project phase: {new_phase.value}")
            
    def log_hours(self, project_id: str, hours: float) -> None:
        """Log hours worked on project"""
        if project_id in self.projects:
            project = self.projects[project_id]
            project.hours_used += hours
            logger.info(f"Logged {hours} hours on {project.title} ({project.get_progress():.1f}% complete)")
            
    def get_active_projects(self) -> List[Project]:
        """Get all active projects"""
        return [
            p for p in self.projects.values()
            if p.phase in [ProjectPhase.ACTIVE, ProjectPhase.DELIVERY]
        ]
        
    def get_project_health(self, project_id: str) -> Dict[str, Any]:
        """Get project health metrics"""
        if project_id not in self.projects:
            return {}
            
        project = self.projects[project_id]
        progress = project.get_progress()
        
        # Calculate health score
        health_score = 100.0
        
        # Penalize if over budget
        if progress > 100:
            health_score -= (progress - 100) * 0.5
            
        # Penalize if behind schedule (simplified)
        if project.end_date and datetime.now() > project.end_date:
            health_score -= 30
            
        health_score = max(0, min(100, health_score))
        
        return {
            "project_id": project_id,
            "progress": progress,
            "remaining_budget": project.get_remaining_budget(),
            "health_score": health_score,
            "status": "healthy" if health_score > 70 else "at_risk" if health_score > 40 else "critical"
        }
        
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        total_value = sum(p.total_value for p in self.projects.values())
        active_value = sum(
            p.total_value for p in self.projects.values()
            if p.phase in [ProjectPhase.ACTIVE, ProjectPhase.DELIVERY]
        )
        
        return {
            "total_projects": len(self.projects),
            "active_projects": len(self.get_active_projects()),
            "total_value": total_value,
            "active_value": active_value,
            "phases": {
                phase.value: sum(1 for p in self.projects.values() if p.phase == phase)
                for phase in ProjectPhase
            }
        }


class ActiveIncomeOptimizer:
    """Main active income optimizer orchestrating all components"""
    
    def __init__(self, base_hourly_rate: float = 100.0):
        self.task_router = FreelanceTaskRouter()
        self.acquisition_pipeline = ClientAcquisitionPipeline()
        self.pricing_engine = PricingEngine(base_hourly_rate)
        self.project_pipeline = ProjectPipeline()
        
    async def process_new_lead(self, lead: Lead) -> Dict[str, Any]:
        """Process new lead through acquisition pipeline"""
        self.acquisition_pipeline.add_lead(lead)
        
        # Auto-contact high-value leads
        if lead.score >= 70:
            lead.contacted_at = datetime.now()
            logger.info(f"Auto-contacted high-value lead: {lead.name}")
            
            # Simulate conversion for demo
            if random.random() > 0.5:
                client = self.acquisition_pipeline.convert_lead(lead.lead_id)
                return {"converted": True, "client": client}
                
        return {"converted": False, "lead": lead}
        
    def create_project_proposal(self,
                               client_id: str,
                               title: str,
                               description: str,
                               estimated_hours: float,
                               complexity: float,
                               urgency: float) -> Dict[str, Any]:
        """Create project proposal with pricing"""
        
        client = self.acquisition_pipeline.clients.get(client_id)
        if not client:
            return {"error": "Client not found"}
            
        # Calculate pricing
        pricing = self.pricing_engine.calculate_project_price(
            estimated_hours=estimated_hours,
            client_tier=client.tier,
            complexity=complexity,
            urgency=urgency
        )
        
        proposal = {
            "client": client.name,
            "title": title,
            "description": description,
            "pricing": pricing,
            "deliverables": [],
            "timeline": f"{estimated_hours / 40:.1f} weeks"
        }
        
        logger.info(f"Created proposal: {title} - ${pricing['total']:.2f}")
        
        return proposal
        
    def accept_project(self,
                      client_id: str,
                      title: str,
                      description: str,
                      total_value: float,
                      hours_allocated: float) -> Project:
        """Accept and create new project"""
        
        project_id = f"PROJ_{len(self.project_pipeline.projects) + 1}"
        
        project = Project(
            project_id=project_id,
            client_id=client_id,
            title=title,
            description=description,
            phase=ProjectPhase.ACTIVE,
            total_value=total_value,
            hours_allocated=hours_allocated,
            start_date=datetime.now()
        )
        
        self.project_pipeline.create_project(project)
        self.acquisition_pipeline.update_client_value(client_id, total_value)
        
        return project
        
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive active income report"""
        return {
            "tasks": self.task_router.get_task_stats(),
            "pipeline": self.acquisition_pipeline.get_pipeline_stats(),
            "projects": self.project_pipeline.get_pipeline_stats(),
            "pricing": {
                "base_rate": self.pricing_engine.base_hourly_rate,
                "total_quotes": len(self.pricing_engine.rate_history)
            }
        }


async def main():
    """Example usage of Active Income Optimizer"""
    
    optimizer = ActiveIncomeOptimizer(base_hourly_rate=150.0)
    
    # Add some leads
    lead1 = Lead(
        lead_id="LEAD_1",
        name="Tech Corp",
        email="contact@techcorp.com",
        company="Tech Corp Inc",
        project_description="AI automation system",
        budget_range=(15000, 25000),
        source="referral"
    )
    
    lead2 = Lead(
        lead_id="LEAD_2",
        name="Startup XYZ",
        email="founder@startupxyz.com",
        company="Startup XYZ",
        project_description="MVP development",
        budget_range=(5000, 10000),
        source="linkedin"
    )
    
    # Process leads
    result1 = await optimizer.process_new_lead(lead1)
    result2 = await optimizer.process_new_lead(lead2)
    
    # Create proposals for converted clients
    if result1.get('converted'):
        client = result1['client']
        proposal = optimizer.create_project_proposal(
            client_id=client.client_id,
            title="AI Automation System",
            description="Build comprehensive AI automation",
            estimated_hours=120,
            complexity=0.8,
            urgency=0.6
        )
        
        # Accept project
        project = optimizer.accept_project(
            client_id=client.client_id,
            title=proposal['title'],
            description=proposal['description'],
            total_value=proposal['pricing']['total'],
            hours_allocated=proposal['pricing']['estimated_hours']
        )
        
        # Add tasks for project
        task = FreelanceTask(
            task_id="TASK_1",
            title="Design AI architecture",
            description="Design system architecture",
            client=client.name,
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            estimated_hours=20,
            hourly_rate=proposal['pricing']['hourly_rate'],
            deadline=datetime.now() + timedelta(days=7),
            skills_required=["AI", "Architecture", "Python"]
        )
        optimizer.task_router.add_task(task)
    
    # Generate report
    report = optimizer.get_comprehensive_report()
    
    print("\n" + "="*60)
    print("ACTIVE INCOME OPTIMIZER - COMPREHENSIVE REPORT")
    print("="*60)
    print(f"\nTasks: {report['tasks']['total_tasks']} (${report['tasks']['total_value']:.2f})")
    print(f"Leads: {report['pipeline']['total_leads']} ({report['pipeline']['conversion_rate']:.1f}% conversion)")
    print(f"Clients: {report['pipeline']['total_clients']} (${report['pipeline']['total_client_value']:.2f} LTV)")
    print(f"Projects: {report['projects']['total_projects']} (${report['projects']['total_value']:.2f})")
    print(f"Base Rate: ${report['pricing']['base_rate']:.2f}/hr")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
