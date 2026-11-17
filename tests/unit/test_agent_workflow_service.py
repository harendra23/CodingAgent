import json

import pytest
from langchain_core.messages import AIMessage

from ai_dev_agent.application.dtos.agent_workflow import AgentWorkflowRequest, CodeGenerationDraft
from ai_dev_agent.application.dtos.requirements_validation import RequirementsAssessment
from ai_dev_agent.application.services import agent_workflow_service as workflow_module
from ai_dev_agent.application.services.agent_workflow_service import (
    AgentWorkflowService,
    WorkflowExecutionError,
)


def build_assessment(score: int) -> RequirementsAssessment:
    categories = {
        name: {"score": score, "rationale": "Compared source evidence."}
        for name in (
            "business_intent",
            "acceptance_criteria",
            "api_contract",
            "technology_stack",
            "security_controls",
            "dependencies",
        )
    }
    if score >= 95:
        classification = "Fully Aligned"
    elif score >= 80:
        classification = "Mostly Aligned"
    elif score >= 60:
        classification = "Partially Aligned"
    else:
        classification = "Misaligned"
    return RequirementsAssessment(
        overall_alignment_score=score,
        classification=classification,
        summary="Requirements assessment.",
        category_scores=categories,
        matched_areas=["Requirement FR-001"],
        material_gaps=[],
        ignored_differences=[],
    )


class FakeRequirementsService:
    def __init__(self, score: int) -> None:
        self.assessment = build_assessment(score)

    async def fetch_requirement_text(self, issue_key: str, page_id: str) -> tuple[str, str]:
        return "Ticket requirement FR-001", "Confluence requirement FR-001"

    async def assess_requirement_text(
        self,
        issue_key: str,
        page_id: str,
        jira_content: str,
        confluence_content: str,
    ) -> RequirementsAssessment:
        return self.assessment


class FakeModel:
    def __init__(self) -> None:
        self.calls = []

    async def ainvoke(self, messages) -> AIMessage:
        self.calls.append(messages)
        return AIMessage(content=f"Draft {len(self.calls)}")

    def with_structured_output(self, schema):
        parent = self

        class StructuredFakeModel:
            async def ainvoke(self, messages):
                parent.calls.append(messages)
                if schema is CodeGenerationDraft:
                    return schema(
                        summary="Adapt the existing implementation.",
                        unified_diff="mock patch",
                    )
                system_prompt = messages[0].content
                return schema(
                    summary="Architecture and workflow draft.",
                    sections=[
                        {
                            "heading": "Affected components",
                            "items": ["Existing API", "Repository service"],
                        }
                    ],
                    mermaid_diagram=(
                        "flowchart LR\n  User --> API\n  API --> Repository"
                        if "Architecture Design" in system_prompt
                        else None
                    ),
                    traceability_rows=[],
                )

        return StructuredFakeModel()


@pytest.mark.asyncio
async def test_workflow_runs_impact_analysis_then_applies_code_draft(monkeypatch, tmp_path) -> None:
    applied_patches: list[str] = []
    monkeypatch.setattr(workflow_module, "clone_github_repository", lambda url, token: tmp_path)
    monkeypatch.setattr(
        workflow_module,
        "repository_context",
        lambda path: "### src/app.py\nExisting implementation",
    )
    monkeypatch.setattr(
        workflow_module,
        "apply_unified_diff",
        lambda path, patch: applied_patches.append(patch) or ["src/app.py", "src/new.py"],
    )
    model = FakeModel()
    trace_path = tmp_path / "workflow-trace.jsonl"
    service = AgentWorkflowService(model, FakeRequirementsService(85), trace_log_path=trace_path)

    result = await service.run("PROJ-7", "701", "https://github.com/acme/example")

    assert result["status"] == "completed"
    assert len(model.calls) == 8
    assert [stage.id for stage in result["stages"]] == [
        "confluence_requirement",
        "requirement_validation",
        "repository_impact_analysis",
        "technical_specification",
        "architecture_design",
        "task_breakdown",
        "code_generation",
        "unit_tests",
        "traceability_matrix",
        "pull_request",
    ]
    assert all(stage.status == "completed" for stage in result["stages"])
    validation_artifact = result["stages"][1].artifact
    assert "85% alignment" in validation_artifact.summary
    assert validation_artifact.sections[0].heading == "Category scores"
    assert "Repository Impact Analysis" in model.calls[0][0].content
    assert "Existing implementation" in model.calls[0][1].content
    assert "Existing implementation" in model.calls[4][1].content
    assert "flowchart LR" in result["stages"][4].artifact.mermaid_diagram
    assert applied_patches == ["mock patch"]
    assert "src/app.py" in result["stages"][6].artifact.sections[0].items
    assert result["stages"][6].code_diff == "mock patch"
    trace_records = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    successful_steps = [
        record["step_id"] for record in trace_records if record["status"] == "success"
    ]
    assert successful_steps == [stage.id for stage in result["stages"]]
    assert len({record["run_id"] for record in trace_records}) == 1


def test_workflow_request_accepts_only_https_github_repository_urls() -> None:
    request = AgentWorkflowRequest(
        jira_issue_key="PROJ-7",
        confluence_page_id="701",
        repository_url="https://github.com/acme/example.git",
    )

    assert request.repository_url.endswith("example.git")
    with pytest.raises(ValueError):
        AgentWorkflowRequest(
            jira_issue_key="PROJ-7",
            confluence_page_id="701",
            repository_url="https://example.com/acme/example",
        )


@pytest.mark.asyncio
async def test_workflow_blocks_drafts_and_skips_clone_below_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_module,
        "clone_github_repository",
        lambda url, token: pytest.fail(
            "Repository must not be cloned below the alignment threshold"
        ),
    )
    model = FakeModel()
    service = AgentWorkflowService(model, FakeRequirementsService(79))

    result = await service.run("PROJ-7", "701", "https://github.com/acme/example")

    assert result["status"] == "blocked"
    assert model.calls == []
    assert [stage.status for stage in result["stages"][:2]] == ["completed", "completed"]
    assert all(stage.status == "skipped" for stage in result["stages"][2:])


@pytest.mark.asyncio
async def test_workflow_reports_repository_clone_failure_stage(monkeypatch, tmp_path) -> None:
    def fail_clone(url: str, token: str | None):
        raise RuntimeError("Unable to clone the GitHub repository. Check the URL and GITHUB_TOKEN.")

    monkeypatch.setattr(workflow_module, "clone_github_repository", fail_clone)
    trace_path = tmp_path / "workflow-trace.jsonl"
    service = AgentWorkflowService(
        FakeModel(),
        FakeRequirementsService(85),
        trace_log_path=trace_path,
    )

    with pytest.raises(WorkflowExecutionError, match="Repository Impact Analysis failed"):
        await service.run("PROJ-7", "701", "https://github.com/acme/example")

    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    failure = next(record for record in records if record["status"] == "failure")
    assert failure["step_id"] == "repository_impact_analysis"
    assert failure["error_description"].startswith("Repository Impact Analysis failed:")


@pytest.mark.asyncio
async def test_workflow_retries_a_git_rejected_diff_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(workflow_module, "clone_github_repository", lambda url, token: tmp_path)
    monkeypatch.setattr(
        workflow_module,
        "repository_context",
        lambda path: "### src/app.py\nVALUE = 'old'",
    )
    patches = iter(["bad patch", "corrected patch"])
    applied: list[str] = []

    def apply_patch(path, patch):
        if patch == "bad patch":
            raise workflow_module.RepositoryPatchError(
                "Git rejected the generated diff: patch failed: src/app.py:1"
            )
        applied.append(patch)
        return ["src/app.py"]

    monkeypatch.setattr(workflow_module, "apply_unified_diff", apply_patch)
    model = FakeModel()

    class RepairModel(FakeModel):
        def with_structured_output(self, schema):
            parent = self

            class StructuredFakeModel:
                async def ainvoke(self, messages):
                    parent.calls.append(messages)
                    if schema is CodeGenerationDraft:
                        patch = next(patches)
                        return schema(summary="Apply reviewed implementation.", unified_diff=patch)
                    return schema(summary="Stage draft.")

            return StructuredFakeModel()

    model = RepairModel()
    result = await AgentWorkflowService(model, FakeRequirementsService(85)).run(
        "PROJ-7", "701", "https://github.com/acme/example"
    )

    assert applied == ["corrected patch"]
    assert "patch failed" in model.calls[5][-1].content
    assert result["stages"][6].code_diff == "corrected patch"