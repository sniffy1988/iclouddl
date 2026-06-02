from __future__ import annotations

import logging
import sys

import click

from iclouddownloader.config import get_settings
from iclouddownloader.db.models import Base
from iclouddownloader.db.session import get_engine, get_session_factory
from iclouddownloader.daemon import run_daemon
from iclouddownloader.icloud.auth import interactive_login
from iclouddownloader.icloud.client import cookie_dir_for_user
from iclouddownloader.main import run_web
from iclouddownloader.services.sync_service import SyncService
from iclouddownloader.services.user_service import UserService
from iclouddownloader.notifications import AppNotifier


@click.group()
def main():
    """iCloud Photo Downloader — multi-user backup with PostgreSQL tracking."""


@main.command("db-init")
def db_init():
    """Create database tables (for dev without Alembic)."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    click.echo("Database tables created.")


@main.command("db-upgrade")
def db_upgrade():
    """Run Alembic migrations to latest revision."""
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    click.echo("Database upgraded to head.")


@main.group()
def user():
    """Manage Apple ID users."""


@user.command("add")
@click.option("--apple-id", required=True)
@click.option("--display-name", default=None)
@click.option("--download-dir", default=None)
@click.option("--interval", "sync_interval_seconds", type=int, default=None)
def user_add(apple_id, display_name, download_dir, sync_interval_seconds):
    db = get_session_factory()()
    try:
        u = UserService(db).create_user(
            apple_id=apple_id,
            display_name=display_name,
            download_dir=download_dir,
            sync_interval_seconds=sync_interval_seconds,
        )
        AppNotifier().user_added(u)
        click.echo(f"Created user id={u.id} apple_id={u.apple_id} dir={u.download_dir}")
    finally:
        db.close()


@user.command("list")
def user_list():
    db = get_session_factory()()
    try:
        for u in UserService(db).list_users():
            click.echo(
                f"{u.id:4d}  {u.apple_id:30s}  enabled={u.enabled}  "
                f"status={u.last_sync_status or '-':12s}  next={u.next_sync_at}"
            )
    finally:
        db.close()


@user.command("enable")
@click.argument("user_id", type=int)
def user_enable(user_id):
    db = get_session_factory()()
    try:
        UserService(db).set_enabled(user_id, True)
        click.echo(f"User {user_id} enabled.")
    finally:
        db.close()


@user.command("fetch-count")
@click.option("--user-id", type=int, required=True)
def user_fetch_count(user_id):
    """Count photos in iCloud without downloading."""
    db = get_session_factory()()
    try:
        result = SyncService(db, notifier=AppNotifier()).fetch_icloud_photo_count(user_id)
        click.echo(
            f"iCloud photos: {result['icloud_photos_count']} | "
            f"downloaded locally: {result['downloaded_count']} | "
            f"remaining: {result.get('remaining_to_download', '—')}"
        )
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)
    finally:
        db.close()


@user.command("disable")
@click.argument("user_id", type=int)
def user_disable(user_id):
    db = get_session_factory()()
    try:
        UserService(db).set_enabled(user_id, False)
        click.echo(f"User {user_id} disabled.")
    finally:
        db.close()


@main.group()
def auth():
    """iCloud authentication."""


@auth.command("login")
@click.option("--apple-id", required=True)
@click.option("--password", prompt=True, hide_input=True)
def auth_login(apple_id, password):
    db = get_session_factory()()
    try:
        svc = UserService(db)
        user = svc.get_by_apple_id(apple_id)
        if not user:
            user = svc.create_user(apple_id=apple_id)
        cookie_dir = cookie_dir_for_user(user.id)
        interactive_login(user, password, cookie_dir)
        from iclouddownloader.services.auth_service import AuthService

        AuthService(db).mark_fully_authenticated(user, from_2fa=True)
        db.commit()
        click.echo(f"Authenticated {apple_id}. Session saved to {cookie_dir}")
    finally:
        db.close()


@main.command("sync")
@click.option("--user-id", type=int, required=True)
def sync_now(user_id):
    db = get_session_factory()()
    try:
        run = SyncService(db, notifier=AppNotifier()).trigger_sync(user_id)
        click.echo(
            f"Sync {run.status.value}: downloaded={run.photos_downloaded} "
            f"failed={run.photos_failed} skipped={run.photos_skipped}"
        )
    finally:
        db.close()


@main.command("status")
@click.option("--limit", default=10)
def status(limit):
    db = get_session_factory()()
    try:
        runs = SyncService(db).list_sync_runs(limit=limit)
        for r in runs:
            click.echo(
                f"run={r.id} user={r.user_id} {r.status.value} "
                f"dl={r.photos_downloaded} fail={r.photos_failed} at={r.started_at}"
            )
        stats = SyncService(db).dashboard_stats()
        click.echo(f"Stats: {stats}")
    finally:
        db.close()


@main.group()
def daemon():
    """Background scheduler."""


@daemon.command("start")
def daemon_start():
    run_daemon()


@main.group()
def web():
    """Web API server."""


@web.command("start")
def web_start():
    run_web()


@main.group()
def telegram():
    """Telegram bot utilities."""


@telegram.command("test")
def telegram_test():
    import asyncio

    notifier = AppNotifier()
    ok = asyncio.run(notifier.test_telegram())
    click.echo("Sent" if ok else "Failed — configure Telegram in Settings (database)")


if __name__ == "__main__":
    main()
