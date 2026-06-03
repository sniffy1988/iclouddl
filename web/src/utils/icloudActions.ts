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

/** User has (or had) an iCloud session worth clearing — not merely an Apple ID on file. */
export function canDisconnectIcloud(user: User): boolean {
  if (!hasSavedAppleId(user)) return false;
  return user.icloud_auth_status !== "not_authorized";
}

export function canCountIcloud(user: User, syncBusy: SyncBusyScopes): boolean {
  if (!hasSavedAppleId(user)) return false;
  if (user.icloud_auth_status !== "authorized") return false;
  if (syncBusy.icloud || syncBusy.all) return false;
  return true;
}

export function canSyncIcloud(user: User, syncBusy: SyncBusyScopes): boolean {
  return canCountIcloud(user, syncBusy);
}
