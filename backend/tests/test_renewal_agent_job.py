import json
import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.run_renewal_agent import (
    WHATSAPP_ENABLED,
    execute_batch,
    max_consecutive_portal_failures,
    missing_client_email_body,
    process_one,
    renewal_cutoff,
    renewal_status_blocks_automation,
    run,
    send_internal_renewal_email,
    should_check_collection_after_failure,
    should_run,
    task_processing_order,
)


class RenewalAgentJobTests(unittest.TestCase):
    def test_collection_check_is_limited_to_known_legacy_portal_failures(self):
        self.assertTrue(
            should_check_collection_after_failure(
                "Locator.wait_for: Timeout 90000ms exceeded."
            )
        )
        self.assertTrue(
            should_check_collection_after_failure(
                "Se esperó una póliza original 123 para RFC123; se encontraron 0"
            )
        )
        self.assertFalse(
            should_check_collection_after_failure("SMTP connection refused")
        )

    def test_old_portal_failure_runs_independent_collection_check(self):
        from adapters.metlife_gmm_collection import MetLifeGmmCollectionResult
        from adapters.metlife_gmm_portal import AdapterStepResult, MetLifeGmmPortalResult

        task = SimpleNamespace(
            id="task-1",
            policy_number="1454602",
            original_policy_number="1454602",
            rfc="BOFK941022ME5",
            client_name="Karla",
            renewal_deadline=date(2026, 9, 10),
            attempt_count=1,
        )
        retrieval_result = MetLifeGmmPortalResult(
            status="failed",
            task_id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            steps=[
                AdapterStepResult(
                    step_name="search_rfc",
                    status="failed",
                    started_at="2026-08-27T09:00:00",
                )
            ],
            error_message="Locator.wait_for: Timeout 90000ms exceeded.",
        )
        collection_result = MetLifeGmmCollectionResult(
            status="completed",
            task_id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            paid_until=date(2026, 9, 10),
            steps=[],
        )

        with patch(
            "jobs.run_renewal_agent.update_task_attempt",
            return_value=task,
        ), patch(
            "jobs.run_renewal_agent.MetLifeGmmOldPortalAdapter",
        ) as old_adapter, patch(
            "jobs.run_renewal_agent.check_metlife_gmm_collection",
            return_value=collection_result,
        ) as collection_check, patch(
            "jobs.run_renewal_agent.persist_collection_check",
            return_value=True,
        ) as persist_collection, patch(
            "jobs.run_renewal_agent.persist_result",
        ), patch(
            "jobs.run_renewal_agent.record_action",
        ), patch(
            "jobs.run_renewal_agent.emit",
        ):
            old_adapter.return_value.run.return_value = retrieval_result
            item, portal_failure = process_one("run-1", task.id)

        collection_check.assert_called_once()
        persist_collection.assert_called_once_with(
            task.id,
            paid_until=date(2026, 9, 10),
            succeeded=True,
            error=None,
        )
        self.assertIn("Pagado Hasta 10/09/2026", item["detail"])
        self.assertIn("Revision Manual Necesaria", item["detail"])
        self.assertFalse(portal_failure)

    def test_failed_collection_check_persists_sentinel_date(self):
        from adapters.metlife_gmm_collection import MetLifeGmmCollectionResult
        from adapters.metlife_gmm_portal import AdapterStepResult, MetLifeGmmPortalResult

        task = SimpleNamespace(
            id="task-2",
            policy_number="12345",
            original_policy_number="12345",
            rfc="RFC123456ABC",
            client_name="Cliente",
            renewal_deadline=date(2026, 9, 10),
            attempt_count=1,
        )
        retrieval_result = MetLifeGmmPortalResult(
            status="failed",
            task_id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            steps=[
                AdapterStepResult(
                    step_name="confirm_policy_match",
                    status="failed",
                    started_at="2026-08-27T09:00:00",
                )
            ],
            error_message="Se esperó una póliza original 12345 para RFC123456ABC",
        )
        collection_result = MetLifeGmmCollectionResult(
            status="failed",
            task_id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            paid_until=None,
            steps=[],
            error_message="La sección Cobranza no cargó",
        )

        with patch(
            "jobs.run_renewal_agent.update_task_attempt",
            return_value=task,
        ), patch(
            "jobs.run_renewal_agent.MetLifeGmmOldPortalAdapter",
        ) as old_adapter, patch(
            "jobs.run_renewal_agent.check_metlife_gmm_collection",
            return_value=collection_result,
        ), patch(
            "jobs.run_renewal_agent.persist_collection_check",
            return_value=False,
        ) as persist_collection, patch(
            "jobs.run_renewal_agent.persist_result",
        ), patch(
            "jobs.run_renewal_agent.record_action",
        ), patch(
            "jobs.run_renewal_agent.emit",
        ):
            old_adapter.return_value.run.return_value = retrieval_result
            item, portal_failure = process_one("run-1", task.id)

        persist_collection.assert_called_once_with(
            task.id,
            paid_until=date(2000, 1, 1),
            succeeded=False,
            error="La sección Cobranza no cargó",
        )
        self.assertIn("Pagado Hasta: 01/01/2000", item["detail"])
        self.assertTrue(portal_failure)

    def test_start_and_close_notices_use_dedicated_renewal_sender(self):
        settings = {"sender": "clientes@taiico.com"}
        with patch(
            "jobs.run_renewal_agent.renewal_smtp_settings",
            return_value=settings,
        ), patch(
            "jobs.run_renewal_agent.internal_recipients",
            return_value=["team@taiico.com"],
        ), patch(
            "jobs.run_renewal_agent.send_email_smtp",
        ) as send_email:
            send_internal_renewal_email(subject="Inicio", body="Resumen")

        send_email.assert_called_once_with(
            subject="Inicio",
            body="Resumen",
            recipients=["team@taiico.com"],
            cc_recipients=[],
            settings=settings,
        )

    def test_retry_query_keeps_failed_attempts_eligible(self):
        source = Path(__file__).resolve().parents[1] / "jobs" / "run_renewal_agent.py"
        contents = source.read_text()
        self.assertIn('PolicyDocumentRetrievalTask.status == "queued"', contents)
        self.assertIn("PolicyDocumentRetrievalTask.attempt_count > 0", contents)

    def test_successful_delivery_uses_final_automatic_status(self):
        source = Path(__file__).resolve().parents[1] / "jobs" / "run_renewal_agent.py"
        self.assertIn(
            'renewal.insurer_response = "Enviado Automáticamente"',
            source.read_text(),
        )

    def test_final_crm_statuses_block_automatic_retry(self):
        for status in (
            "Renovado Automático",
            "Renovada Manual",
            "Enviada Manual",
            "Enviada al cliente",
            "Enviado Automáticamente",
            "Revision Manual Necesaria",
            "Enviado",
        ):
            with self.subTest(status=status):
                self.assertTrue(renewal_status_blocks_automation(status))
        self.assertFalse(renewal_status_blocks_automation(None))
        self.assertFalse(renewal_status_blocks_automation("Pendiente de envío"))

    def test_automatic_delivery_uses_dedicated_renewal_sender(self):
        source = Path(__file__).resolve().parents[1] / "jobs" / "run_renewal_agent.py"
        self.assertIn("settings=renewal_smtp_settings()", source.read_text())

    def test_job_runs_once_after_09_mexico_city(self):
        now = datetime(
            2026,
            7,
            28,
            9,
            5,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_AUTOMATION_HOUR": "9"},
        ):
            self.assertTrue(should_run(now, None))
            self.assertFalse(should_run(now, "2026-07-28"))

    def test_job_does_not_run_before_09(self):
        now = datetime(
            2026,
            7,
            28,
            8,
            59,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_AUTOMATION_HOUR": "9"},
        ):
            self.assertFalse(should_run(now, None))

    def test_cutoff_is_dynamic_thirty_day_window(self):
        now = datetime(
            2026,
            7,
            28,
            9,
            0,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_AUTOMATION_WINDOW_DAYS": "30"},
        ):
            self.assertEqual(renewal_cutoff(now), date(2026, 8, 27))

    def test_whatsapp_is_disabled_in_daily_job(self):
        self.assertFalse(WHATSAPP_ENABLED)

    def test_missing_client_email_message_is_explicit(self):
        body = missing_client_email_body(
            client_name="Cliente Sin Correo",
            policy_number="12345",
            renewal_deadline=date(2026, 9, 5),
        )

        self.assertIn("No tenemos un correo de cliente registrado", body)
        self.assertIn("Hola Cliente Sin Correo", body)
        self.assertIn("periodo 2026 - 2027", body)
        self.assertIn("Póliza de referencia: 12345", body)
        self.assertIn("Saludos,\nTAIICO", body)

    def test_default_abort_threshold_is_seven_consecutive_failures(self):
        with patch.dict(os.environ):
            os.environ.pop(
                "RENEWAL_AGENT_MAX_CONSECUTIVE_PORTAL_FAILURES",
                None,
            )
            self.assertEqual(max_consecutive_portal_failures(), 7)

    def test_overdue_tasks_are_processed_after_current_window_tasks(self):
        class Task:
            def __init__(self, deadline, policy_number):
                self.renewal_deadline = deadline
                self.policy_number = policy_number
                self.attempt_count = 0

        process_date = date(2026, 7, 31)
        tasks = [
            Task(date(2026, 7, 20), "OVERDUE"),
            Task(date(2026, 8, 5), "UPCOMING"),
            Task(date(2026, 7, 31), "TODAY"),
        ]

        ordered = sorted(
            tasks,
            key=lambda task: task_processing_order(task, process_date),
        )

        self.assertEqual(
            [task.policy_number for task in ordered],
            ["TODAY", "UPCOMING", "OVERDUE"],
        )

    def test_batch_aborts_on_seventh_consecutive_portal_failure(self):
        now = datetime(
            2026,
            7,
            31,
            9,
            0,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        tasks = [
            SimpleNamespace(
                id=f"task-{index}",
                policy_number=f"policy-{index}",
                renewal_deadline=date(2026, 8, 1),
                client_name=f"Cliente {index}",
                rfc=f"RFC{index}",
            )
            for index in range(8)
        ]
        failure = (
            {
                "status": "failed",
                "detail": "No se encontró la renovación en el portal",
            },
            True,
        )
        completed = {
            "run_id": "run-1",
            "status": "failed",
            "selected": 8,
            "succeeded": 0,
            "failed": 7,
            "aborted": True,
        }

        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_MAX_CONSECUTIVE_PORTAL_FAILURES": "7"},
        ), patch(
            "jobs.run_renewal_agent.selected_tasks",
            return_value=tasks,
        ), patch(
            "jobs.run_renewal_agent.create_run",
            return_value="run-1",
        ), patch(
            "jobs.run_renewal_agent.send_email_smtp",
        ) as send_email, patch(
            "jobs.run_renewal_agent.renewal_smtp_settings",
            return_value={"sender": "clientes@taiico.com"},
        ), patch(
            "jobs.run_renewal_agent.process_one_subprocess",
            return_value=failure,
        ) as process_one_subprocess, patch(
            "jobs.run_renewal_agent.finish_run",
            return_value=completed,
        ) as finish_run:
            result = execute_batch(now)

        send_email.assert_called_once()
        self.assertEqual(
            send_email.call_args.kwargs["settings"]["sender"],
            "clientes@taiico.com",
        )
        self.assertEqual(process_one_subprocess.call_count, 7)
        finish_run.assert_called_once_with(
            "run-1",
            [failure[0]] * 7,
            aborted=True,
            process_date=now.date(),
        )
        self.assertEqual(result, completed)

    def test_batch_honors_explicit_limit(self):
        now = datetime(
            2026,
            7,
            31,
            9,
            0,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        tasks = [
            SimpleNamespace(
                id=f"task-{index}",
                policy_number=f"policy-{index}",
                renewal_deadline=date(2026, 8, 1),
                client_name=f"Cliente {index}",
                rfc=f"RFC{index}",
            )
            for index in range(8)
        ]
        completed = {
            "run_id": "run-1",
            "status": "completed",
            "selected": 5,
            "succeeded": 5,
            "failed": 0,
            "aborted": False,
        }

        with patch(
            "jobs.run_renewal_agent.selected_tasks",
            return_value=tasks,
        ), patch(
            "jobs.run_renewal_agent.create_run",
            return_value="run-1",
        ) as create_run, patch(
            "jobs.run_renewal_agent.send_email_smtp",
        ) as send_email, patch(
            "jobs.run_renewal_agent.renewal_smtp_settings",
            return_value={"sender": "clientes@taiico.com"},
        ), patch(
            "jobs.run_renewal_agent.process_one_subprocess",
            return_value=({"status": "completed"}, False),
        ) as process_one_subprocess, patch(
            "jobs.run_renewal_agent.finish_run",
            return_value=completed,
        ):
            result = execute_batch(now, limit=5)

        send_email.assert_called_once()
        self.assertEqual(
            send_email.call_args.kwargs["settings"]["sender"],
            "clientes@taiico.com",
        )
        self.assertEqual(result, completed)
        self.assertEqual(process_one_subprocess.call_count, 5)
        self.assertEqual(len(create_run.call_args.args[0]), 5)

    def test_started_date_is_written_before_batch_and_prevents_second_run(self):
        now = datetime(
            2026,
            7,
            28,
            9,
            5,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "RENEWAL_AGENT_AUTOMATION_STATE_FILE": (
                    f"{directory}/state.json"
                )
            },
        ), patch(
            "jobs.run_renewal_agent.local_now",
            return_value=now,
        ), patch(
            "jobs.run_renewal_agent.execute_batch",
            return_value={
                "run_id": "run-1",
                "status": "completed",
                "selected": 1,
                "succeeded": 1,
                "failed": 0,
                "aborted": False,
            },
        ) as execute:
            self.assertEqual(run(), 0)
            self.assertEqual(run(), 0)
            state = json.loads(Path(directory, "state.json").read_text())

        execute.assert_called_once()
        self.assertEqual(state["last_started_date"], "2026-07-28")
        self.assertFalse(state["whatsapp_enabled"])


if __name__ == "__main__":
    unittest.main()
