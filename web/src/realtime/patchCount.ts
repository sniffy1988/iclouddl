import type { QueryClient } from "@tanstack/react-query";
import type { PhotoSource, User } from "../api/client";

export function countingStatus(source: PhotoSource): string {
  return source === "google_photos" ? "counting_google" : "counting_icloud";
}

/** Optimistic / WS-aligned cache update when a count job starts. */
export function patchCountStarted(
  qc: QueryClient,
  userId: number,
  source: PhotoSource
): void {
  const status = countingStatus(source);
  const patchUser = (u: User): User => {
    const next: User = { ...u, activity_status: status, last_sync_status: status };
    if (source === "icloud") next.icloud_photos_count = 0;
    if (source === "google_photos") next.google_photos_count = 0;
    return next;
  };
  qc.setQueryData<User[]>(["users"], (old) =>
    old?.map((u) => (u.id === userId ? patchUser(u) : u)) ?? old
  );
  qc.setQueryData<User>(["user", userId], (old) => (old ? patchUser(old) : old));
  qc.setQueryData(["photo-counts", userId], (old: unknown) => {
    if (!old || typeof old !== "object") return old;
    const counts = { ...(old as Record<string, unknown>) };
    if (source === "icloud") counts.icloud_photos_count = 0;
    else counts.google_photos_count = 0;
    return counts;
  });
}
