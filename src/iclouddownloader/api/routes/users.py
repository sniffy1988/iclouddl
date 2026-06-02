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
    TriggerSyncResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from iclouddownloader.services.sync_service import SyncInProgressError
from iclouddownloader.db.models import AuthChallengeStatus
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
    fetch_count: bool = True,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    svc = UserService(db)
    if svc.get_by_apple_id(body.apple_id):
        raise HTTPException(400, "Apple ID already registered")
    user = svc.create_user(**body.model_dump())

    if fetch_count:

        def _count(uid: int):
            from iclouddownloader.db.session import get_session_factory

            sdb = get_session_factory()()
            try:
                SyncService(sdb).fetch_icloud_photo_count(uid)
            except Exception:
                pass
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

    for user in user_svc.list_users():
        if not user.enabled:
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
    library_id = ImmichClient.library_id_for_user(user)
    if not library_id:
        return {"ok": False, "message": "Link an external library ID on this user first"}
    if not client.configured:
        return {"ok": False, "message": "Configure Immich in Settings first"}
    ok, message = await client.test_connection(library_id)
    return {"ok": ok, "message": message}


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _: None = Depends(require_auth)):
    UserService(db).delete_user(user_id)


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
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    sync_svc = SyncService(db)
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if not user.enabled:
        raise HTTPException(400, "User is disabled")

    if user.last_sync_status == "counting":
        return FetchCountResponse(
            ok=False,
            message="Photo count already in progress",
            user_id=user_id,
            already_running=True,
        )

    try:
        sync_svc.ensure_can_start_sync(user_id)
    except SyncInProgressError:
        return FetchCountResponse(
            ok=False,
            message="Sync is in progress — wait for it to finish before counting",
            user_id=user_id,
            already_running=True,
        )

    def _run():
        from iclouddownloader.db.session import get_session_factory

        sdb = get_session_factory()()
        try:
            SyncService(sdb).fetch_icloud_photo_count(user_id)
        finally:
            sdb.close()

    background_tasks.add_task(_run)
    return FetchCountResponse(ok=True, message="Fetching photo count from iCloud", user_id=user_id)


@router.post("/{user_id}/sync", response_model=TriggerSyncResponse)
def trigger_sync(
    user_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    sync_svc = SyncService(db)
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if not user.enabled:
        raise HTTPException(400, "User is disabled — enable before syncing")

    try:
        sync_svc.ensure_can_start_sync(user_id)
    except SyncInProgressError as e:
        return TriggerSyncResponse(
            ok=False,
            message="Sync already in progress for this user",
            user_id=user_id,
            sync_run_id=e.sync_run_id,
            already_running=True,
        )

    sync_svc.mark_sync_queued(user_id)
    notifier = AppNotifier()

    def _run():
        from iclouddownloader.db.session import get_session_factory

        sdb = get_session_factory()()
        try:
            SyncService(sdb, notifier=notifier).trigger_sync(user_id)
        finally:
            sdb.close()

    background_tasks.add_task(_run)
    return TriggerSyncResponse(
        ok=True,
        message="Sync job started",
        user_id=user_id,
    )


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
