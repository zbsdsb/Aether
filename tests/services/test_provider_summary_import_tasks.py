from __future__ import annotations

from src.api.admin.providers.summary import _summarize_provider_import_tasks
from src.models.database import ProviderImportTask


def test_summarize_provider_import_tasks_aggregates_actionable_states() -> None:
    tasks = [
        ProviderImportTask(
            id="task-pending-1",
            provider_id="provider-import-1",
            endpoint_id="endpoint-import-1",
            task_type="pending_reissue",
            status="pending",
            source_kind="all_in_hub",
            source_id="acct-pending",
            source_name="Pending Source",
            source_origin="https://provider-import-1.example.com",
            credential_payload="enc-pending",
            source_metadata={"site_type": "new-api"},
        ),
        ProviderImportTask(
            id="task-waiting-1",
            provider_id="provider-import-1",
            endpoint_id="endpoint-import-1",
            task_type="pending_reissue",
            status="waiting_plaintext",
            source_kind="all_in_hub",
            source_id="acct-waiting",
            source_name="Waiting Source",
            source_origin="https://provider-import-1.example.com",
            credential_payload="enc-waiting",
            source_metadata={"site_type": "new-api"},
        ),
        ProviderImportTask(
            id="task-failed-1",
            provider_id="provider-import-1",
            endpoint_id="endpoint-import-1",
            task_type="pending_import",
            status="failed",
            source_kind="all_in_hub",
            source_id="acct-failed",
            source_name="Failed Source",
            source_origin="https://provider-import-1.example.com",
            credential_payload="enc-failed",
            source_metadata={"site_type": "anyrouter"},
        ),
        ProviderImportTask(
            id="task-completed-1",
            provider_id="provider-import-1",
            endpoint_id="endpoint-import-1",
            task_type="pending_reissue",
            status="completed",
            source_kind="all_in_hub",
            source_id="acct-completed",
            source_name="Completed Source",
            source_origin="https://provider-import-1.example.com",
            credential_payload="enc-completed",
            source_metadata={"site_type": "new-api"},
        ),
    ]

    summary = _summarize_provider_import_tasks(tasks)

    assert summary.import_task_total == 4
    assert summary.import_task_pending == 1
    assert summary.import_task_waiting_plaintext == 1
    assert summary.import_task_failed == 1
    assert summary.import_task_last_status == "waiting_plaintext"
    assert summary.needs_manual_key_input is True
    assert summary.needs_manual_review is True
