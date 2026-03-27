from clone_scale_engine import TaskCloner


def test_generate_derivative_tasks_returns_three_required_clones():
    cloner = TaskCloner()
    completed = {
        "task_id": "task-123",
        "prompt": "Design a contract review workflow",
        "output": "Created baseline workflow with validation",
    }

    clones = cloner.generate_derivative_tasks(completed)

    assert len(clones) == 3
    clone_types = {item["clone_type"] for item in clones}
    assert clone_types == {"deeper_dive", "cross_domain_clone", "meta_analysis"}


def test_generated_clones_reference_original_task_and_have_prompt():
    cloner = TaskCloner(default_target_domain="healthcare")
    completed = {
        "task_id": "task-999",
        "prompt": "Optimize support triage",
        "output": "Introduced tiered escalation rules",
    }

    clones = cloner.generate_derivative_tasks(completed)

    for clone in clones:
        assert clone["original_task_id"] == "task-999"
        assert isinstance(clone["prompt"], str)
        assert "task-999" in clone["prompt"]
        assert clone["prompt"].strip() != ""

    cross_domain = next(item for item in clones if item["clone_type"] == "cross_domain_clone")
    assert cross_domain["domain_adaptation_rules"]["target_domain"] == "healthcare"
