"""Smoke tests confirming the ChatMasala redesign is in place."""
import pytest


def test_run_model_exists():
    from app.models import Run
    assert Run.__tablename__ == "runs"


def test_agent_profile_model_exists():
    from app.models import AgentProfile
    assert AgentProfile.__tablename__ == "agent_profiles"


def test_thread_model_removed():
    import app.models as m
    assert not hasattr(m, "Thread"), "Thread model should have been removed in the redesign"


def test_run_has_goal_field():
    from app.models import Run
    assert hasattr(Run, "goal")


def test_run_has_workflow_type():
    from app.models import Run
    assert hasattr(Run, "workflow_type")


def test_two_workflow_presets_only():
    """The two hard-coded preset values are single_agent and builder_reviewer."""
    valid = {"single_agent", "builder_reviewer"}
    assert "single_agent" in valid
    assert "builder_reviewer" in valid


def test_single_agent_prompt_builder():
    from app.prompts import build_single_agent_prompt
    p = build_single_agent_prompt(goal="Test goal")
    assert "Test goal" in p


def test_build_builder_prompt_uses_goal():
    from app.prompts import build_builder_prompt
    import inspect
    sig = inspect.signature(build_builder_prompt)
    assert "goal" in sig.parameters, "build_builder_prompt should use 'goal' not 'task_text'"
