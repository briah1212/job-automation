"""End-to-end integration tests against the real dockerized stack (postgres,
minio, api, mock-ats, browser-worker). Run with:

    docker compose up -d
    pip install -r tests/integration/requirements.txt
    pytest tests/integration -v

Each test drives the system exactly the way a real user/frontend would - only
through the public API - and inspects Postgres directly to assert on state
that isn't otherwise observable, matching how this suite's scenarios were
originally verified by hand during development.
"""
import time

from conftest import (
    ensure_fixture_resume_file,
    get_browser_status,
    poll_until,
    restart_browser_worker_container,
    wait_for_workflow_status,
)


class TestFullSubmission:
    def test_full_run_reaches_submitted_confirmation(self, resume_attached_application):
        """The complete golden path: landing through every state to a real
        confirmed submission, exercising the whole BrowserState machine in
        one pass."""
        ensure_fixture_resume_file()
        app = resume_attached_application
        client = app["client"]

        start = client.post(f"/api/applications/{app['application_id']}/start-browser")
        assert start.status_code == 201, start.text

        status = wait_for_workflow_status(
            client, app["application_id"], "waiting_user_input", "reach a pause point (question or approval)"
        )
        # The mock ATS form includes a field (willing_to_relocate) with no
        # canonical mapping, so a first-time run for a fresh user legitimately
        # pauses on a dynamic question before it can reach awaiting_approval.
        if status["current_step"] == "paused_question":
            answer = client.post(
                f"/api/applications/{app['application_id']}/answer-pending-question",
                json={"answer_text": "yes"},
            )
            assert answer.status_code == 200, answer.text
            status = wait_for_workflow_status(
                client, app["application_id"], "waiting_user_input", "reach awaiting_approval after answering"
            )

        assert status["current_step"] == "awaiting_approval", status

        approve = client.post(f"/api/applications/{app['application_id']}/approve-submit")
        assert approve.status_code == 200, approve.text

        final = wait_for_workflow_status(client, app["application_id"], "completed", "reach completed/submitted")
        assert final["task_metadata"]["confirmed"] is True
        assert final["task_metadata"]["application_id"].startswith("MOCK-")


class TestManualIntervention:
    def test_missing_resume_pauses_then_resumes_after_fix(self, user, db_conn):
        """Generic manual-intervention framework test: no ATS-specific
        trigger, just a precondition failure (no resume attached) that any
        real ATS run could hit. Verifies pause -> external fix -> explicit
        resume -> continues without restarting from scratch."""
        client = user["client"]

        job_response = client.post("/api/jobs/import-url", json={"url": "http://mock-ats:8080"})
        assert job_response.status_code < 300, job_response.text
        job_id = job_response.json()["id"]
        app_response = client.post("/api/applications", json={"job_id": job_id})
        assert app_response.status_code < 300, app_response.text
        application_id = app_response.json()["id"]
        # deliberately no resume attached yet

        start = client.post(f"/api/applications/{application_id}/start-browser")
        assert start.status_code == 201, start.text

        paused = wait_for_workflow_status(
            client, application_id, "waiting_user_input", "pause for manual intervention (missing resume)"
        )
        assert paused["current_step"] == "manual_intervention"
        assert paused["task_metadata"]["pause_reason"] == "repeated_failure"

        # Fix the underlying problem externally, then resume via the generic endpoint.
        ensure_fixture_resume_file()
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resume_families (id, user_id, name, status, created_at, updated_at)
                VALUES (gen_random_uuid(), %s, 'MI Family', 'ready', now(), now()) RETURNING id
                """,
                (user["user_id"],),
            )
            family_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO resume_versions (id, family_id, version, status, file_path, parsed_data, created_at, updated_at)
                VALUES (gen_random_uuid(), %s, 1, 'ready', 'resumes/integration-test/resume.pdf', '{}', now(), now())
                RETURNING id
                """,
                (family_id,),
            )
            resume_version_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE applications SET resume_version_id = %s WHERE id = %s",
                (resume_version_id, application_id),
            )

        resume = client.post(f"/api/applications/{application_id}/resume-manual-intervention")
        assert resume.status_code == 200, resume.text

        # It must transition through "running" and back to "waiting_user_input"
        # at a *different* step than before - not stay stuck on the same pause.
        def _progressed():
            current = get_browser_status(client, application_id)
            if current["status"] == "waiting_user_input" and current["current_step"] != "manual_intervention":
                return current
            return None

        progressed = poll_until(_progressed, description="progress past resume_upload after resuming")
        assert progressed["current_step"] in ("paused_question", "awaiting_approval")

    def test_resume_endpoint_rejects_when_not_paused(self, resume_attached_application):
        """Can't resume a task that was never started."""
        app = resume_attached_application
        response = app["client"].post(f"/api/applications/{app['application_id']}/resume-manual-intervention")
        assert response.status_code == 404


class TestDynamicQuestions:
    def test_unmapped_field_pauses_and_answer_completes_it(self, resume_attached_application):
        """willing_to_relocate has no FieldMapper canonical mapping and no
        prior ReusableAnswer for a fresh user, so it must pause with a
        well-formed pending_question rather than silently skip the field."""
        ensure_fixture_resume_file()
        app = resume_attached_application
        client = app["client"]

        client.post(f"/api/applications/{app['application_id']}/start-browser")

        status = wait_for_workflow_status(
            client, app["application_id"], "waiting_user_input", "pause on dynamic question"
        )
        assert status["current_step"] == "paused_question"
        pending = status["task_metadata"]["pending_question"]
        assert pending["field_name"] == "willing_to_relocate"
        assert pending["label"]

        answer = client.post(
            f"/api/applications/{app['application_id']}/answer-pending-question",
            json={"answer_text": "yes"},
        )
        assert answer.status_code == 200, answer.text

        def _reached_approval():
            current = get_browser_status(client, app["application_id"])
            return current if current["current_step"] == "awaiting_approval" else None

        resumed = poll_until(_reached_approval, description="continue past the answered question to awaiting_approval")
        assert resumed["status"] == "waiting_user_input"

    def test_answering_a_question_creates_a_reusable_answer(self, resume_attached_application, db_conn):
        ensure_fixture_resume_file()
        app = resume_attached_application
        client = app["client"]
        client.post(f"/api/applications/{app['application_id']}/start-browser")
        wait_for_workflow_status(client, app["application_id"], "waiting_user_input", "pause on dynamic question")
        client.post(
            f"/api/applications/{app['application_id']}/answer-pending-question",
            json={"answer_text": "yes"},
        )
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT exact_answer, user_approved FROM reusable_answers WHERE user_id = %s",
                (app["user_id"],),
            )
            rows = cur.fetchall()
        assert any(r[0] == "yes" and r[1] is True for r in rows)


class TestFieldLearning:
    def test_regex_matched_fields_are_recorded_and_reused(self, resume_attached_application, db_conn):
        ensure_fixture_resume_file()
        app = resume_attached_application
        client = app["client"]
        client.post(f"/api/applications/{app['application_id']}/start-browser")
        wait_for_workflow_status(
            client, app["application_id"], "waiting_user_input", "task reaches its first pause point"
        )

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT field_name, canonical_name, use_count FROM field_mappings WHERE field_name = 'first_name'"
            )
            row = cur.fetchone()
        assert row is not None, "first_name mapping should have been learned"
        assert row[1] == "first_name"
        assert row[2] >= 1


class TestCredentialReuse:
    def test_second_application_reuses_credential_and_logs_in(self, user, db_conn):
        """The core "learned once, reused forever" property for ATS accounts:
        a second application for the same user against the same tenant must
        take the LOGIN branch, not create a second account."""
        ensure_fixture_resume_file()
        client = user["client"]

        def make_application():
            job = client.post("/api/jobs/import-url", json={"url": "http://mock-ats:8080"}).json()
            app_resp = client.post("/api/applications", json={"job_id": job["id"]}).json()
            application_id = app_resp["id"]
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO resume_families (id, user_id, name, status, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, 'CR Family', 'ready', now(), now()) RETURNING id
                    """,
                    (user["user_id"],),
                )
                family_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO resume_versions (id, family_id, version, status, file_path, parsed_data, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, 1, 'ready', 'resumes/integration-test/resume.pdf', '{}', now(), now())
                    RETURNING id
                    """,
                    (family_id,),
                )
                resume_version_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE applications SET resume_version_id = %s WHERE id = %s",
                    (resume_version_id, application_id),
                )
            return application_id

        first_app = make_application()
        client.post(f"/api/applications/{first_app}/start-browser")
        wait_for_workflow_status(
            client, first_app, "waiting_user_input", "first application reaches a pause point"
        )
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ats_credentials WHERE user_id = %s", (user["user_id"],))
            count_after_first = cur.fetchone()[0]
        assert count_after_first == 1

        second_app = make_application()
        client.post(f"/api/applications/{second_app}/start-browser")
        wait_for_workflow_status(
            client, second_app, "waiting_user_input", "second application reaches a pause point"
        )

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT browser_state FROM browser_sessions WHERE session_key = %s", (f"app_{second_app}",)
            )
            browser_state = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM ats_credentials WHERE user_id = %s", (user["user_id"],))
            count_after_second = cur.fetchone()[0]

        assert browser_state != "create_account", "second application should have logged in, not signed up again"
        assert count_after_second == 1, "a second application must reuse the existing credential, not create another"


class TestContainerRestartRecovery:
    def test_paused_task_survives_browser_worker_restart(self, resume_attached_application):
        """The durability property the whole checkpoint system exists for:
        a container recreation must not lose a paused session's progress."""
        ensure_fixture_resume_file()
        app = resume_attached_application
        client = app["client"]

        client.post(f"/api/applications/{app['application_id']}/start-browser")
        before = wait_for_workflow_status(
            client, app["application_id"], "waiting_user_input", "reach a pause point before restarting"
        )

        restart_browser_worker_container()
        time.sleep(8)  # let the poll loop come back up

        after = get_browser_status(client, app["application_id"])
        assert after["status"] == before["status"]
        assert after["current_step"] == before["current_step"]

        before_updated_at = before["task_metadata"].get("updated_at")

        # And it must still be resumable post-restart, not stuck.
        if after["current_step"] == "paused_question":
            client.post(
                f"/api/applications/{app['application_id']}/answer-pending-question",
                json={"answer_text": "yes"},
            )
        else:
            client.post(f"/api/applications/{app['application_id']}/resume-manual-intervention")

        def _progressed():
            current = get_browser_status(client, app["application_id"])
            return current if current["task_metadata"].get("updated_at") != before_updated_at else None

        progressed = poll_until(_progressed, description="task progresses after post-restart resume")
        assert progressed is not None
