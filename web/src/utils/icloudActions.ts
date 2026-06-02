import type { User } from "../api/client";

export type SyncBusyScopes = {
  icloud?: boolean;
  google_photos?: boolean;
  all?: boolean;
};

/** Apple ID stored on the user (save Storage & profile first if only typed in the form). */
export function hasSavedAppleId(user: User): boolean {
  return Boolean(user.apple_id?.trim());
}

export function canCountIcloud(user: User, syncBusy: SyncBusyScopes): boolean {
  if (!hasSavedAppleId(user)) return false;
  if (user.icloud_auth_status === "awaiting_2fa") return false;
  if (syncBusy.icloud) return false;
  return true;
}

export function canSyncIcloud(user: User, syncBusy: SyncBusyScopes): boolean {
  if (!canCountIcloud(user, syncBusy)) return false;
  return user.icloud_auth_status === "authorized";
}
