export interface SyncEvent {
  type: string;
  user_id?: number | null;
  apple_id?: string | null;
  account_label?: string | null;
  source?: string | null;
  scope?: string | null;
  sync_run_id?: number | null;
  payload?: Record<string, unknown>;
  timestamp?: string;
}
