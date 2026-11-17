import json

from ai_dev_agent.infrastructure.logging.workflow_trace import WorkflowTrace


def test_trace_file_records_ordered_status_and_redacts_secrets(tmp_path) -> None:
    log_path = tmp_path / "workflow-trace.jsonl"
    trace = WorkflowTrace("run-123", log_path)
    trace.record(
        step_order=2,
        step_id="repository_impact_analysis",
        step_name="Repository Impact Analysis",
        status="started",
    )
    trace.record(
        step_order=2,
        step_id="repository_impact_analysis",
        step_name="Repository Impact Analysis",
        status="failure",
        error=RuntimeError("GITHUB_TOKEN=never-log-this"),
    )

    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert [record["status"] for record in records] == ["started", "failure"]
    assert [record["step_order"] for record in records] == [2, 2]
    assert all(record["run_id"] == "run-123" for record in records)
    assert all(record["level"] == "TRACE" for record in records)
    assert records[1]["error_type"] == "RuntimeError"
    assert "[REDACTED]" in records[1]["error_description"]
    assert "never-log-this" not in log_path.read_text(encoding="utf-8")
