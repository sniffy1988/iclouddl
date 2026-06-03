import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.api.schemas import (
    AuthChallengeRequest,
    AuthChallengeResponse,
    UserICloudLoginRequest,
    UserICloudLoginResponse,
    FetchCountResponse,
    PhotoCountResponse,
    CancelSyncResponse,
    TriggerSyncResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from iclouddownloader.services.sync_service import SyncInProgressError
from iclouddownloader.db.models import AuthChallengeStatus, PhotoSource
from iclouddownloader.providers.base import scope_for_source
from iclouddownloader.api.schemas import PhotoSourceParam
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.sync_service import SyncService
from iclouddownloader.services.user_service import UserService
from iclouddownloader.notifications import AppNotifier

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    sync_svc = SyncService(db)
    return [sync_svc.user_to_response(u) for u in UserService(db).list_users()]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    fetch_count: bool = False,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    svc = UserService(db)
    if body.apple_id and svc.get_by_apple_id(body.apple_id):
        raise HTTPException(400, "Apple ID already registered")
    if not body.apple_id and not body.display_name:
        raise HTTPException(400, "Provide apple_id and/or display_name")
    user = svc.create_user(**body.model_dump())
    notifier = AppNotifier()
    notifier.user_added(user)

    if fetch_count and user.apple_id and AuthService(db).is_authorized(user):

        def _count(uid: int):
            from iclouddownloader.db.session import get_session_factory

            sdb = get_session_factory()()
            try:
                SyncService(sdb, notifier=notifier).fetch_icloud_photo_count(uid)
            except Exception:
                u = UserService(sdb).get_user(uid)
                if u and u.last_sync_status in (
                    "counting",
                    "counting_icloud",
                    "counting_google",
                ):
                    u.last_sync_status = "idle"
                    sdb.commit()
            finally:
                sdb.close()

        background_tasks.add_task(_count, user.id)

    return SyncService(db).user_to_response(user)


@router.post("/fetch-all-counts")
def fetch_all_photo_counts(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Fetch iCloud photo count for every enabled user (no download)."""
    sync_svc = SyncService(db)
    user_svc = UserService(db)
    queued: list[int] = []

    auth_svc = AuthService(db)
    for user in user_svc.list_users():
        if not user.enabled:
            continue
        if not user.apple_id or not auth_svc.is_authorized(user):
            continue
        if user.last_sync_status == "counting":
            continue
        if sync_svc.get_active_sync_run(user.id):
            continue
        queued.append(user.id)

    def _run(uid: int):
        from iclouddownloader.db.session import get_session_factory

        sdb = get_session_factory()()
        try:
            SyncService(sdb).fetch_icloud_photo_count(uid)
        except Exception:
            pass
        finally:
            sdb.close()

    for uid in queued:
        user = user_svc.get_user(uid)
        if user:
            user.last_sync_status = "counting"
    db.commit()

    for uid in queued:
        background_tasks.add_task(_run, uid)

    return {
        "ok": True,
        "queued": queued,
        "message": f"Fetching photo count for {len(queued)} user(s)",
    }


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return SyncService(db).user_to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    try:
        payload = body.model_dump(exclude_unset=True)
        user = UserService(db).update_user(user_id, **payload)
        return SyncService(db).user_to_response(user)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/{user_id}/immich/test")
async def test_user_immich(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    from iclouddownloader.integrations.immich import ImmichClient

    client = ImmichClient()
    if not client.enabled:
        raise HTTPException(400, "Immich integration is disabled in Settings")
    library_id = ImmichClient.library_id_for_user(user)
    if not library_id:
        return {"ok": False, "message": "Link an external library ID on this user first"}
    if not client.configured:
        return {"ok": False, "message": "Configure Immich in Settings first"}
    ok, message = await client.test_connection(library_id)
    return {"ok": ok, "message": message}


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    svc = UserService(db)
    user = svc.get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    AppNotifier().user_removed(user)
    svc.delete_user(user_id)


@router.get("/{user_id}/photo-counts", response_model=PhotoCountResponse)
def get_photo_counts(user_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return SyncService(db).build_photo_count_result(user)


@router.post("/{user_id}/fetch-count", response_model=FetchCountResponse)
def fetch_photo_count(
    user_id: int,
    background_tasks: BackgroundTasks,
    source: PhotoSourceParam = "icloud",
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    sync_svc = SyncService(db)
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    photo_source = PhotoSource(source)
    counting_status = (
        "counting_icloud" if photo_source == PhotoSource.icloud else "counting_google"
    )
    if user.last_sync_status in ("counting", counting_status):
        return FetchCountResponse(
            ok=False,
            message="Photo count already in progress",
            user_id=user_id,
            source=source,
            already_running=True,
        )

    if photo_source == PhotoSource.icloud and not AuthService(db).is_authorized(user):
        raise HTTPException(400, "Authorize iCloud before counting photos")

    try:
        sync_svc.ensure_can_start_sync(user_id, requested=photo_source)
    except SyncInProgressError as e:
        return FetchCountResponse(
            ok=False,
            message=f"Sync in progress (scope={e.scope}) — wait before counting",
            user_id=user_id,
            source=source,
            already_running=True,
        )

    notifier = AppNotifier()

    def _run(src: PhotoSource = photo_source):
        from iclouddownloader.db.session import get_session_factory

        sdb = get_session_factory()()
        try:
            SyncService(sdb, notifier=notifier).fetch_photo_count(user_id, src)
        finally:
            sdb.close()

    background_tasks.add_task(_run)
    label = "iCloud" if photo_source == PhotoSource.icloud else "Google Photos"
    return FetchCountResponse(
        ok=True,
        message=f"Fetching photo count from {label}",
        user_id=user_id,
        source=source,
    )


@router.post("/{user_id}/sync", response_model=TriggerSyncResponse)
def trigger_sync(
    user_id: int,
    background_tasks: BackgroundTasks,
    source: PhotoSourceParam | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    sync_svc = SyncService(db)
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    photo_source = PhotoSource(source) if source else None
    scope = scope_for_source(photo_source)

    try:
        sync_svc.ensure_can_start_sync(user_id, requested=photo_source)
    except SyncInProgressError as e:
        return TriggerSyncResponse(
            ok=False,
            message=f"Sync already in progress (scope={e.scope})",
            user_id=user_id,
            source=source,
            scope=e.scope,
            sync_run_id=e.sync_run_id,
            already_running=True,
        )

    sync_svc.mark_sync_queued(user_id)
    notifier = AppNotifier()

    def _run(src: PhotoSource | None = photo_source):
        from iclouddownloader.db.session import get_session_factory

        sdb = get_session_factory()()
        try:
            SyncService(sdb, notifier=notifier).trigger_sync(user_id, source=src)
        finally:
            sdb.close()

    background_tasks.add_task(_run)
    return TriggerSyncResponse(
        ok=True,
        message="Sync job started",
        user_id=user_id,
        source=source,
        scope=scope.value,
    )


@router.post("/{user_id}/sync/cancel", response_model=CancelSyncResponse)
def cancel_sync(
    user_id: int,
    source: PhotoSourceParam | None = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    photo_source = PhotoSource(source) if source else None
    try:
        result = SyncService(db).request_cancel_sync(user_id, photo_source)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return CancelSyncResponse(**result)


@router.post("/{user_id}/auth/icloud/disconnect")
def disconnect_icloud(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    sync_svc = SyncService(db)
    for run in sync_svc.get_active_sync_runs(user_id):
        if run.scope.value in ("icloud", "all"):
            raise HTTPException(
                409,
                "Cannot disconnect iCloud while an iCloud or full sync is running",
            )
    try:
        AuthService(db).disconnect_icloud(user)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


@router.post("/{user_id}/auth/login", response_model=UserICloudLoginResponse)
def start_icloud_login(
    user_id: int,
    body: UserICloudLoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    try:
        result = AuthService(db).start_authentication(user_id, body.password)
        return UserICloudLoginResponse(**result)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/{user_id}/auth/challenge", response_model=AuthChallengeResponse | None)
def get_pending_challenge(user_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    challenge = AuthService(db).get_pending_challenge(user_id)
    if not challenge:
        return None
    return challenge


@router.post("/{user_id}/auth/challenge")
def submit_challenge(
    user_id: int,
    body: AuthChallengeRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    log = logging.getLogger(__name__)
    try:
        challenge = AuthService(db).submit_challenge_code(
            user_id, body.code, body.challenge_id, password=body.password
        )
        return {"ok": True, "status": challenge.status.value}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        log.exception("2FA submit failed for user_id=%s", user_id)
        raise HTTPException(400, f"Verification failed: {e}") from e
