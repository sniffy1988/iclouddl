import type { QueryClient } from "@tanstack/react-query";
import type { PhotoCounts, SyncRun, User } from "../api/client";
import type { SyncEvent } from "./types";

function num(payload: Record<string, unknown>, key: string): number | undefined {
  const v = Number(payload[key]);
  return Number.isFinite(v) ? v : undefined;
}

export function patchSyncStarted(qc: QueryClient, userId: number): void {
  const patchUser = (u: User): User => ({
    ...u,
    activity_status: "syncing",
    last_sync_status: "syncing",
  });
  qc.setQueryData<User[]>(["users"], (old) =>
    old?.map((u) => (u.id === userId ? patchUser(u) : u)) ?? old
  );
  qc.setQueryData<User>(["user", userId], (old) => (old ? patchUser(old) : old));
}

export function patchSyncProgress(
  qc: QueryClient,
  userId: number,
  event: SyncEvent
): void {
  const payload = event.payload ?? {};
  const downloadedCount = num(payload, "downloaded_count");
  const remaining = num(payload, "remaining_to_download");
  const icloudRemaining = num(payload, "icloud_remaining");
  const googleRemaining = num(payload, "google_remaining");
  const icloudDownloaded = num(payload, "icloud_downloaded_count");
  const googleDownloaded = num(payload, "google_downloaded_count");
  const icloudTotal = num(payload, "icloud_photos_count");
  const googleTotal = num(payload, "google_photos_count");

  const patchUser = (u: User): User => {
    const next: User = {
      ...u,
      activity_status: "syncing",
      last_sync_status: "syncing",
    };
    if (downloadedCount != null) next.downloaded_count = downloadedCount;
    if (icloudDownloaded != null) next.icloud_downloaded_count = icloudDownloaded;
    if (googleDownloaded != null) next.google_downloaded_count = googleDownloaded;
    if (remaining != null) next.remaining_to_download = remaining;
    if (icloudRemaining != null) next.icloud_remaining = icloudRemaining;
    if (googleRemaining != null) next.google_remaining = googleRemaining;
    if (icloudTotal != null) next.icloud_photos_count = icloudTotal;
    if (googleTotal != null) next.google_photos_count = googleTotal;
    return next;
  };

  qc.setQueryData<User[]>(["users"], (old) =>
    old?.map((u) => (u.id === userId ? patchUser(u) : u)) ?? old
  );
  qc.setQueryData<User>(["user", userId], (old) => (old ? patchUser(old) : old));

  qc.setQueryData<PhotoCounts>(["photo-counts", userId], (old) => {
    const base = old ?? ({ user_id: userId } as PhotoCounts);
    return {
      ...base,
      ...(downloadedCount != null ? { downloaded_count: downloadedCount } : {}),
      ...(remaining != null ? { remaining_to_download: remaining } : {}),
      ...(icloudRemaining != null ? { icloud_remaining: icloudRemaining } : {}),
      ...(googleRemaining != null ? { google_remaining: googleRemaining } : {}),
      ...(icloudTotal != null ? { icloud_photos_count: icloudTotal } : {}),
      ...(googleTotal != null ? { google_photos_count: googleTotal } : {}),
    };
  });

  const runId = event.sync_run_id;
  if (runId != null) {
    const runDownloaded = num(payload, "downloaded");
    const runFailed = num(payload, "failed");
    const runSkipped = num(payload, "skipped");
    const runDiscovered = num(payload, "discovered");
    qc.setQueryData<SyncRun[]>(["sync-runs", userId], (old) =>
      old?.map((r) =>
        r.id === runId
          ? {
              ...r,
              status: "running",
              ...(runDownloaded != null ? { photos_downloaded: runDownloaded } : {}),
              ...(runFailed != null ? { photos_failed: runFailed } : {}),
              ...(runSkipped != null ? { photos_skipped: runSkipped } : {}),
              ...(runDiscovered != null ? { photos_discovered: runDiscovered } : {}),
            }
          : r
      ) ?? old
    );
  }

  const runDownloaded = num(payload, "downloaded");
  if (runDownloaded != null && runDownloaded > 0 && runDownloaded % 10 === 0) {
    void qc.invalidateQueries({ queryKey: ["photos", userId] });
  }
}
