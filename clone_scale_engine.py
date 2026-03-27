from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CloneTemplate:
    original_task_id: str
    clone_type: str
    domain_adaptation_rules: Dict[str, Any]
    prompt_template: str


class TaskCloner:
    """Generates derivative tasks from a completed task output."""

    CLONE_DEEPER_DIVE = "deeper_dive"
    CLONE_CROSS_DOMAIN = "cross_domain_clone"
    CLONE_META = "meta_analysis"

    def __init__(self, default_target_domain: str = "real_estate") -> None:
        self.default_target_domain = default_target_domain

    def generate_derivative_tasks(
        self,
        completed_task_output: Dict[str, Any],
        target_domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        task_id = str(completed_task_output.get("task_id", "unknown_task"))
        original_prompt = str(completed_task_output.get("prompt", ""))
        output_summary = str(completed_task_output.get("output", ""))
        domain = target_domain or self.default_target_domain

        templates = [
            self._build_deeper_dive_template(task_id, original_prompt, output_summary),
            self._build_cross_domain_template(task_id, original_prompt, output_summary, domain),
            self._build_meta_analysis_template(task_id, original_prompt, output_summary),
        ]

        return [self._template_to_task_payload(template) for template in templates]

    def _template_to_task_payload(self, template: CloneTemplate) -> Dict[str, Any]:
        return {
            "original_task_id": template.original_task_id,
            "clone_type": template.clone_type,
            "domain_adaptation_rules": template.domain_adaptation_rules,
            "prompt": template.prompt_template,
        }

    def _build_deeper_dive_template(
        self,
        task_id: str,
        original_prompt: str,
        output_summary: str,
    ) -> CloneTemplate:
        prompt = (
            "Deeper-dive task: Expand the completed work with edge-case coverage, failure-mode "
            "analysis, stress scenarios, and mitigation strategies.\n\n"
            f"Original task id: {task_id}\n"
            f"Original prompt: {original_prompt}\n"
            f"Current output: {output_summary}\n"
            "Deliver: risk matrix, edge-case test list, and implementation adjustments."
        )
        return CloneTemplate(
            original_task_id=task_id,
            clone_type=self.CLONE_DEEPER_DIVE,
            domain_adaptation_rules={"mode": "same_domain", "focus": "edge_cases"},
            prompt_template=prompt,
        )

    def _build_cross_domain_template(
        self,
        task_id: str,
        original_prompt: str,
        output_summary: str,
        target_domain: str,
    ) -> CloneTemplate:
        prompt = (
            "Cross-domain clone task: Adapt the completed work into a new domain while preserving "
            "core objective and constraints.\n\n"
            f"Original task id: {task_id}\n"
            f"Original prompt: {original_prompt}\n"
            f"Current output: {output_summary}\n"
            f"Target domain: {target_domain}\n"
            "Deliver: adapted problem framing, translated assumptions, and domain-specific risks."
        )
        return CloneTemplate(
            original_task_id=task_id,
            clone_type=self.CLONE_CROSS_DOMAIN,
            domain_adaptation_rules={
                "mode": "cross_domain",
                "target_domain": target_domain,
                "preserve_intent": True,
            },
            prompt_template=prompt,
        )

    def _build_meta_analysis_template(
        self,
        task_id: str,
        original_prompt: str,
        output_summary: str,
    ) -> CloneTemplate:
        prompt = (
            "Meta-analysis task: Evaluate output quality, completeness, and reliability, then propose "
            "targeted improvements for next iteration.\n\n"
            f"Original task id: {task_id}\n"
            f"Original prompt: {original_prompt}\n"
            f"Current output: {output_summary}\n"
            "Deliver: quality scorecard, missing-information audit, and prioritized improvement plan."
        )
        return CloneTemplate(
            original_task_id=task_id,
            clone_type=self.CLONE_META,
            domain_adaptation_rules={"mode": "meta", "focus": "quality_improvement"},
            prompt_template=prompt,
        )
