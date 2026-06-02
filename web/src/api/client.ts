const API = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = (err as { detail?: string | { msg: string }[] }).detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join(", ")
          : res.statusText;
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface User {
  id: number;
  apple_id: string;
  display_name: string | null;
  download_dir: string;
  sync_interval_seconds: number;
  enabled: boolean;
  library_key: string;
  telegram_notify: boolean;
  next_sync_at: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  auth_status: string;
  activity_status: string;
  icloud_photos_count: number | null;
  icloud_photos_count_at: string | null;
  downloaded_count: number;
  remaining_to_download: number | null;
  icloud_authenticated_at: string | null;
  icloud_2fa_at: string | null;
  icloud_session_ok_at: string | null;
  icloud_needs_auth: boolean;
  icloud_authorized: boolean;
  icloud_2fa_expires_at: string | null;
  days_until_2fa_expires: number | null;
  immich_library_id: string | null;
  immich_scan_after_sync: boolean;
}

export interface ImmichLibrary {
  id: string;
  name: string;
  importPaths: string[];
}

export interface PhotoCounts {
  user_id: number;
  icloud_photos_count: number | null;
  icloud_photos_count_at: string | null;
  downloaded_count: number;
  tracked_count: number;
  remaining_to_download: number | null;
}

export interface SyncRun {
  id: number;
  user_id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  photos_discovered: number;
  photos_downloaded: number;
  photos_failed: number;
  photos_skipped: number;
  error_summary: string | null;
}

export interface Photo {
  id: number;
  filename: string;
  status: string;
  local_path: string | null;
  file_size: number | null;
  downloaded_at: string | null;
}

export interface TriggerSyncResult {
  ok: boolean;
  message: string;
  user_id: number;
  sync_run_id?: number | null;
  already_running?: boolean;
}

export interface TriggerDueResult {
  ok: boolean;
  queued: number[];
  skipped_already_running: number[];
  message: string;
}

export interface SettingsData {
  telegram_enabled: boolean;
  telegram_bot_token_set: boolean;
  telegram_bot_token_masked: string;
  telegram_admin_chat_id: string;
  telegram_allowed_user_ids: string;
  download_path_template: string;
  default_sync_interval_seconds: number;
  max_concurrent_downloads: number;
  scheduler_poll_seconds: number;
  base_download_dir: string;
  immich_enabled: boolean;
  immich_base_url: string;
  immich_api_key_set: boolean;
  immich_api_key_masked: string;
  immich_scan_debounce_seconds: number;
}

export interface DashboardStats {
  total_users: number;
  enabled_users: number;
  total_photos: number;
  downloaded_today: number;
  active_syncs: number;
  failed_syncs: number;
  users_due_for_sync: number;
}

export const api = {
  login: (password: string) =>
    request<{ ok: boolean }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request<{ authenticated: boolean }>("/auth/me"),
  users: () => request<User[]>("/users"),
  getUser: (id: number) => request<User>(`/users/${id}`),
  createUser: (data: Partial<User> & { apple_id: string }, fetchCount = true) =>
    request<User>(`/users?fetch_count=${fetchCount}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  fetchAllPhotoCounts: () =>
    request<{ ok: boolean; queued: number[]; message: string }>("/users/fetch-all-counts", {
      method: "POST",
    }),
  updateUser: (id: number, data: Partial<User> & { reschedule_sync?: boolean }) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  testUserImmich: (id: number) =>
    request<{ ok: boolean; message: string }>(`/users/${id}/immich/test`, { method: "POST" }),
  deleteUser: (id: number) => request<void>(`/users/${id}`, { method: "DELETE" }),
  triggerSync: (id: number) =>
    request<TriggerSyncResult>(`/users/${id}/sync`, { method: "POST" }),
  fetchPhotoCount: (id: number) =>
    request<{ ok: boolean; message: string; already_running?: boolean }>(
      `/users/${id}/fetch-count`,
      { method: "POST" }
    ),
  photoCounts: (id: number) => request<PhotoCounts>(`/users/${id}/photo-counts`),
  triggerDueSyncs: () =>
    request<TriggerDueResult>("/sync/trigger-due", { method: "POST" }),
  startICloudAuth: (id: number, password: string) =>
    request<{
      ok: boolean;
      status: string;
      message: string;
      challenge_type?: string;
      challenge_id?: number;
    }>(`/users/${id}/auth/login`, {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  submit2FA: (id: number, code: string, challengeId?: number, password?: string) =>
    request<{ ok: boolean }>(`/users/${id}/auth/challenge`, {
      method: "POST",
      body: JSON.stringify({ code, challenge_id: challengeId, password }),
    }),
  getPendingChallenge: (id: number) =>
    request<{ id: number; status: string } | null>(`/users/${id}/auth/challenge`),
  syncRuns: (params?: { user_id?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.user_id) q.set("user_id", String(params.user_id));
    if (params?.limit) q.set("limit", String(params.limit));
    return request<SyncRun[]>(`/sync-runs?${q}`);
  },
  photos: (userId: number, limit = 50) =>
    request<Photo[]>(`/users/${userId}/photos?limit=${limit}`),
  stats: () => request<DashboardStats>("/dashboard/stats"),
  settings: () => request<SettingsData>("/settings"),
  updateSettings: (
    data: Partial<SettingsData> & { telegram_bot_token?: string; immich_api_key?: string }
  ) => request<SettingsData>("/settings", { method: "PATCH", body: JSON.stringify(data) }),
  testTelegram: () => request<{ ok: boolean }>("/telegram/test", { method: "POST" }),
  testImmich: (libraryId?: string) =>
    request<{ ok: boolean; message: string }>("/immich/test", {
      method: "POST",
      body: JSON.stringify(libraryId ? { library_id: libraryId } : {}),
    }),
  immichLibraries: () =>
    request<{ libraries: ImmichLibrary[] }>("/immich/libraries"),
};
