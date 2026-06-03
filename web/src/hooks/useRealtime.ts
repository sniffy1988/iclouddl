import { createContext, useContext } from "react";
import type { SyncEvent } from "../realtime/types";

export type RealtimeStatus = "connecting" | "connected" | "reconnecting" | "offline";

export interface RealtimeContextValue {
  status: RealtimeStatus;
  lastEventAt: number | null;
  recentEvents: string[];
  pushEvent: (line: string) => void;
}

export const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export function useRealtime(): RealtimeContextValue {
  const ctx = useContext(RealtimeContext);
  if (!ctx) {
    throw new Error("useRealtime must be used within RealtimeProvider");
  }
  return ctx;
}

/** Poll interval when WebSocket is down; false disables polling while connected. */
export function realtimeRefetchInterval(
  status: RealtimeStatus,
  activeFallback?: boolean
): number | false {
  if (status === "connected") return false;
  if (activeFallback) return 3000;
  return 60000;
}

/** Poll when WebSocket is down (avoid overwriting live WS patches while connected). */
export function useRealtimeRefetchInterval(
  activeFallback?: boolean,
  countingFallback?: boolean,
  syncingFallback?: boolean
): number | false {
  const { status } = useRealtime();
  if (status === "connected") return false;
  if (countingFallback || syncingFallback || activeFallback) return 3000;
  return 60000;
}

export type { SyncEvent };
