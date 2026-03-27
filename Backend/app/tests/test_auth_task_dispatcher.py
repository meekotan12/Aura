"""Use: Tests auth task dispatcher behavior.
Where to use: Use this when running `pytest` to check that this backend behavior still works.
Role: Test layer. It protects the app from regressions.
"""

from fastapi import BackgroundTasks

from app.services import auth_task_dispatcher
from app.workers import tasks as worker_tasks
from app.workers.celery_app import celery_app


def test_dispatch_mfa_code_email_uses_celery_when_available(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_validate() -> None:
        return None

    def fake_apply_async(*, args, kwargs, retry) -> None:
        calls.append((tuple(args), dict(kwargs)))
        assert retry is False

    monkeypatch.setattr(auth_task_dispatcher, "validate_email_delivery_settings", fake_validate)
    monkeypatch.setattr(
        auth_task_dispatcher.send_login_mfa_code_email,
        "apply_async",
        fake_apply_async,
    )

    background_tasks = BackgroundTasks()
    mode = auth_task_dispatcher.dispatch_mfa_code_email(
        background_tasks,
        recipient_email="user@example.com",
        code="123456",
        first_name="Test",
        system_name="VALID8",
    )

    assert mode == "celery"
    assert len(background_tasks.tasks) == 0
    assert calls == [
        (
            ("user@example.com", "123456", "Test", "VALID8"),
            {},
        )
    ]


def test_dispatch_mfa_code_email_falls_back_to_background_task(monkeypatch) -> None:
    def fake_validate() -> None:
        return None

    def fake_apply_async(*, args, kwargs, retry) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(auth_task_dispatcher, "validate_email_delivery_settings", fake_validate)
    monkeypatch.setattr(
        auth_task_dispatcher.send_login_mfa_code_email,
        "apply_async",
        fake_apply_async,
    )

    background_tasks = BackgroundTasks()
    mode = auth_task_dispatcher.dispatch_mfa_code_email(
        background_tasks,
        recipient_email="user@example.com",
        code="123456",
    )

    assert mode == "background"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is auth_task_dispatcher.send_mfa_code_email


def test_dispatch_account_security_notification_falls_back_to_background_task(monkeypatch) -> None:
    def fake_apply_async(*, args, kwargs, retry) -> None:
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        auth_task_dispatcher.send_login_security_notification,
        "apply_async",
        fake_apply_async,
    )

    background_tasks = BackgroundTasks()
    mode = auth_task_dispatcher.dispatch_account_security_notification(
        background_tasks,
        user_id=7,
        subject="New Login Detected",
        message="Security event.",
        metadata_json={"event": "login"},
    )

    assert mode == "background"
    assert len(background_tasks.tasks) == 1


def test_worker_tasks_only_register_canonical_names() -> None:
    canonical_names = {
        "app.workers.tasks.process_student_import_job",
        "app.workers.tasks.send_login_mfa_code_email",
        "app.workers.tasks.send_login_security_notification",
        "app.workers.tasks.send_student_import_onboarding_email",
        "app.workers.tasks.send_student_welcome_email",
        "app.workers.tasks.sync_event_workflow_statuses",
    }
    legacy_names = {
        "app.worker.tasks.process_student_import_job",
        "app.worker.tasks.send_login_mfa_code_email",
        "app.worker.tasks.send_login_security_notification",
        "app.worker.tasks.send_student_import_onboarding_email",
        "app.worker.tasks.send_student_welcome_email",
        "app.worker.tasks.sync_event_workflow_statuses",
    }

    assert worker_tasks.process_student_import_job.name == (
        "app.workers.tasks.process_student_import_job"
    )
    assert worker_tasks.send_login_mfa_code_email.name == (
        "app.workers.tasks.send_login_mfa_code_email"
    )
    assert worker_tasks.send_login_security_notification.name == (
        "app.workers.tasks.send_login_security_notification"
    )
    assert worker_tasks.send_student_import_onboarding_email.name == (
        "app.workers.tasks.send_student_import_onboarding_email"
    )
    assert worker_tasks.send_student_welcome_email.name == (
        "app.workers.tasks.send_student_welcome_email"
    )
    assert worker_tasks.sync_event_workflow_statuses.name == (
        "app.workers.tasks.sync_event_workflow_statuses"
    )
    assert canonical_names.issubset(set(celery_app.tasks))
    assert legacy_names.isdisjoint(set(celery_app.tasks))
