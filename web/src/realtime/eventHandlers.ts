import type { QueryClient } from "@tanstack/react-query";
import type { PhotoSource, User } from "../api/client";
import type { SyncEvent } from "./types";
import { patchCountStarted } from "./patchCount";
import { patchSyncProgress, patchSyncStarted } from "./patchSync";

function sourceFromEvent(event: SyncEvent): PhotoSource {
  return event.source === "google_photos" ? "google_photos" : "icloud";
}

function payloadIndexed(payload: Record<string, unknown>): number {
  const n = Number(payload.indexed);
  return Number.isFinite(n) ? n : 0;
}

function patchUserCounts(
  user: User,
  event: SyncEvent,
  indexed: number
): User {
  const next = { ...user };
  if (event.source === "google_photos") {
    next.google_photos_count = indexed;
  } else {
    next.icloud_photos_count = indexed;
  }
  return next;
}

function patchUsersList(
  qc: QueryClient,
  userId: number,
  patch: (u: User) => User
) {
  qc.setQueryData<User[]>(["users"], (old) =>
    old?.map((u) => (u.id === userId ? patch(u) : u)) ?? old
  );
}

function patchUserDetail(qc: QueryClient, userId: number, patch: (u: User) => User) {
  qc.setQueryData<User>(["user", userId], (old) => (old ? patch(old) : old));
}

export function applySyncEvent(qc: QueryClient, event: SyncEvent): void {
  if (event.type === "realtime.connected") return;

  const userId = event.user_id;
  if (userId == null) return;
  const payload = event.payload ?? {};

  switch (event.type) {
    case "count.started": {
      patchCountStarted(qc, userId, sourceFromEvent(event));
      if (!qc.getQueryData<User>(["user", userId])) {
        void qc.refetchQueries({ queryKey: ["user", userId] });
      }
      break;
    }
    case "count.progress": {
      const indexed = payloadIndexed(payload);
      const countingStatus =
        event.source === "google_photos" ? "counting_google" : "counting_icloud";
      const patch = (u: User) => {
        const next = patchUserCounts(u, event, indexed);
        return {
          ...next,
          activity_status: countingStatus,
          last_sync_status: countingStatus,
        };
      };
      patchUsersList(qc, userId, patch);
      patchUserDetail(qc, userId, patch);
      qc.setQueryData(["photo-counts", userId], (old: unknown) => {
        if (!old || typeof old !== "object") return old;
        const counts = old as Record<string, unknown>;
        if (event.source === "google_photos") {
          return { ...counts, google_photos_count: indexed };
        }
        return { ...counts, icloud_photos_count: indexed };
      });
      if (indexed > 0 && indexed % 10 === 0) {
        void qc.invalidateQueries({ queryKey: ["photos", userId] });
      }
      break;
    }
    case "count.completed": {
      const patch = (u: User) => {
        const next: User = {
          ...u,
          activity_status: "count_ready",
          last_sync_status: "count_ready",
        };
        if (typeof payload.icloud_remaining === "number") {
          next.icloud_remaining = payload.icloud_remaining as number;
        }
        if (typeof payload.google_remaining === "number") {
          next.google_remaining = payload.google_remaining as number;
        }
        if (typeof payload.remaining_to_download === "number") {
          next.remaining_to_download = payload.remaining_to_download as number;
        }
        if (typeof payload.icloud_photos_count === "number") {
          next.icloud_photos_count = payload.icloud_photos_count as number;
        }
        if (typeof payload.google_photos_count === "number") {
          next.google_photos_count = payload.google_photos_count as number;
        }
        const indexed = payloadIndexed(payload);
        if (indexed > 0 || payload.indexed != null) {
          return patchUserCounts(next, event, indexed);
        }
        return next;
      };
      patchUsersList(qc, userId, patch);
      patchUserDetail(qc, userId, patch);
      qc.invalidateQueries({ queryKey: ["photo-counts", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      break;
    }
    case "count.failed": {
      const patch = (u: User) => ({
        ...u,
        activity_status: "idle",
        last_sync_status: "count_failed",
        icloud_needs_auth:
          payload.error === "auth_required" ? true : u.icloud_needs_auth,
      });
      patchUsersList(qc, userId, patch);
      patchUserDetail(qc, userId, patch);
      break;
    }
    case "sync.started": {
      patchSyncStarted(qc, userId);
      void qc.invalidateQueries({ queryKey: ["sync-runs", userId] });
      break;
    }
    case "sync.progress": {
      patchSyncProgress(qc, userId, event);
      break;
    }
    case "sync.completed":
    case "sync.failed":
    case "sync.cancelled": {
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["photo-counts", userId] });
      qc.invalidateQueries({ queryKey: ["sync-runs", userId] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      break;
    }
    default:
      break;
  }
  if (event.type.startsWith("auth.")) {
    qc.invalidateQueries({ queryKey: ["users"] });
    qc.invalidateQueries({ queryKey: ["user", userId] });
    qc.invalidateQueries({ queryKey: ["challenge", userId] });
  }
}
