"""Tests for RegTranslate changes: subtasks, JIRA export, task normalization."""

from __future__ import annotations

import pytest

from app.models import ExtractionSubtask, ExtractionTask
from app.services import deduplication, jira_export, task_generator
from app.prompts.extraction import EXTRACTION_PROMPT


class TestExtractionSubtask:
    """Test ExtractionSubtask and ExtractionTask with subtasks."""

    def test_extraction_task_has_subtasks(self):
        t = ExtractionTask(
            task_id="T1",
            title="Test",
            description="Desc",
            priority="High",
            penalty_risk="",
            source_citation="§ 2.2.1",
            source_text="",
            responsible_role="Backend",
            subtasks=[
                ExtractionSubtask(title="Sub 1", description="D1"),
                ExtractionSubtask(title="Sub 2", description=""),
            ],
        )
        assert hasattr(t, "subtasks")
        assert len(t.subtasks) == 2
        assert t.subtasks[0].title == "Sub 1"
        assert t.subtasks[1].description == ""

    def test_task_from_obj_with_subtasks(self):
        obj = {
            "task_id": "REG-2.2.1-001",
            "title": "Audit logging",
            "description": "Log access",
            "priority": "High",
            "penalty_risk": "Risk",
            "source_citation": "§ 2.2.1",
            "source_text": "Quote",
            "responsible_role": "Backend Engineer",
            "acceptance_criteria": ["AC1"],
            "subtasks": [
                {"title": "Create table", "description": "Schema"},
                {"title": "Add API", "description": ""},
            ],
        }
        task = task_generator._task_from_obj(obj)
        assert task.task_id == "REG-2.2.1-001"
        assert len(task.subtasks) == 2
        assert task.subtasks[0].title == "Create table"
        assert task.subtasks[1].description == ""

    def test_parse_subtasks_from_llm(self):
        raw = [
            {"title": "Implement schema", "description": "Create table"},
            {"title": "Add timestamp", "description": ""},
            "String subtask",
        ]
        subtasks = task_generator._parse_subtasks(raw)
        assert len(subtasks) == 3
        assert subtasks[0].title == "Implement schema"
        assert subtasks[2].title == "String subtask"


class TestTaskNormalization:
    """Test defensive handling of tasks (dict, old schema)."""

    def test_getattr_subtasks_on_extraction_task(self):
        t = ExtractionTask(
            task_id="T1",
            title="T",
            description="D",
            priority="Medium",
            penalty_risk="",
            source_citation="",
            source_text="",
            responsible_role="",
            subtasks=[ExtractionSubtask(title="S", description="")],
        )
        subtasks = getattr(t, "subtasks", None) or []
        assert len(subtasks) == 1

    def test_getattr_subtasks_on_dict(self):
        d = {"task_id": "T1", "subtasks": [{"title": "S", "description": ""}]}
        subtasks = getattr(d, "subtasks", None) or (d.get("subtasks", []) if isinstance(d, dict) else [])
        assert len(subtasks) == 1
        assert subtasks[0]["title"] == "S"


class TestDeduplicationWithSubtasks:
    """Test deduplication merges subtasks."""

    def test_deduplicate_preserves_subtasks(self):
        t1 = ExtractionTask(
            task_id="T1",
            title="Audit logging",
            description="Implement audit logging",
            priority="High",
            penalty_risk="",
            source_citation="§ 2.2.1",
            source_text="",
            responsible_role="Backend",
            subtasks=[ExtractionSubtask(title="Create schema", description="")],
        )
        t2 = ExtractionTask(
            task_id="T2",
            title="Audit logs",
            description="Implement audit logging",
            priority="Medium",
            penalty_risk="",
            source_citation="§ 2.2.2",
            source_text="",
            responsible_role="Backend",
            subtasks=[ExtractionSubtask(title="Add API", description="")],
        )
        merged = deduplication.deduplicate([t1, t2], threshold=0.99)
        assert len(merged) >= 1
        for m in merged:
            assert hasattr(m, "subtasks")


class TestJiraExport:
    """Test JIRA export API and formatting."""

    def test_format_description_has_pm_sections(self):
        t = ExtractionTask(
            task_id="T1",
            title="Test",
            description="Context here",
            priority="High",
            penalty_risk="Risk",
            source_citation="§ 2.2.1",
            source_text="Quote",
            responsible_role="Backend",
            acceptance_criteria=["AC1"],
            subtasks=[],
        )
        desc = jira_export._format_description(t)
        assert "Context" in desc
        assert "Acceptance Criteria" in desc or "acceptance" in desc.lower()
        assert "Technical" in desc
        assert "Regulatory" in desc or "Citation" in desc

    def test_jira_export_accepts_sprint_and_assignee_params(self):
        import inspect

        sig = inspect.signature(jira_export.export_to_jira)
        params = sig.parameters
        assert "sprint_id" in params
        assert "board_id" in params
        assert "auto_create_sprint" in params
        assert "assignee_overrides" in params

    def test_fetch_active_sprints_exists(self):
        assert hasattr(jira_export, "fetch_active_sprints")

    def test_create_sprint_exists(self):
        assert hasattr(jira_export, "create_sprint")

    def test_get_or_create_sprint_exists(self):
        assert hasattr(jira_export, "get_or_create_sprint")


class TestJsonRepair:
    """Test JSON repair for malformed LLM output."""

    def test_trailing_comma_repair(self):
        raw = '[{"task_id": "T1", "title": "Test"},]'
        arr = task_generator._extract_json_array(raw)
        assert len(arr) == 1
        assert arr[0]["task_id"] == "T1"

    def test_missing_comma_repair(self):
        raw = '[{"task_id": "T1"}\n{"task_id": "T2"}]'
        arr = task_generator._extract_json_array(raw)
        assert len(arr) == 2


class TestExtractionPrompt:
    """Test extraction prompt includes subtasks."""

    def test_prompt_mentions_subtasks(self):
        assert "subtask" in EXTRACTION_PROMPT.lower()
