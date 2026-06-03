import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import {
  RealtimeContext,
  type RealtimeContextValue,
  type RealtimeStatus,
} from "../hooks/useRealtime";
import { applySyncEvent } from "../realtime/eventHandlers";
import type { SyncEvent } from "../realtime/types";

const MAX_BACKOFF_MS = 30_000;
const OFFLINE_BANNER_MS = 10_000;

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/ws`;
}

function formatEventLine(event: SyncEvent, t: TFunction): string {
  const label = event.account_label || event.apple_id || String(event.user_id ?? "");
  const payload = event.payload ?? {};
  if (event.type === "realtime.connected") {
    return t("realtime.connected");
  }
  if (event.type === "count.started") {
    return t("dashboard.eventCountStarted", {
      user: label,
      source: event.source === "google_photos" ? "Google" : "iCloud",
    });
  }
  if (event.type === "count.progress") {
    const indexed = Number(payload.indexed);
    if (!Number.isFinite(indexed)) {
      return `${event.type} ${label}`.trim();
    }
    return t("dashboard.eventCountProgress", {
      user: label,
      source: event.source === "google_photos" ? "Google" : "iCloud",
      indexed,
    });
  }
  if (event.type === "sync.progress") {
    const downloaded = Number(payload.downloaded);
    if (!Number.isFinite(downloaded)) {
      return `${event.type} ${label}`.trim();
    }
    return t("dashboard.eventSyncProgress", {
      user: label,
      downloaded,
      failed: Number(payload.failed) || 0,
    });
  }
  if (event.type === "count.completed") {
    const total =
      typeof payload.icloud_photos_count === "number"
        ? payload.icloud_photos_count
        : typeof payload.google_photos_count === "number"
          ? payload.google_photos_count
          : typeof payload.indexed === "number"
            ? payload.indexed
            : "—";
    return t("dashboard.eventCountDone", {
      user: label,
      source: event.source === "google_photos" ? "Google" : "iCloud",
      total,
    });
  }
  return `${event.type} ${label}`.trim();
}

export default function RealtimeProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [status, setStatus] = useState<RealtimeStatus>("connecting");
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);
  const [recentEvents, setRecentEvents] = useState<string[]>([]);
  const [showOfflineBanner, setShowOfflineBanner] = useState(true);
  const [offlineSince, setOfflineSince] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const pushEvent = useCallback((line: string) => {
    setRecentEvents((prev) => [line, ...prev].slice(0, 20));
  }, []);

  const handleMessage = useCallback(
    (raw: string) => {
      let event: SyncEvent;
      try {
        event = JSON.parse(raw) as SyncEvent;
      } catch {
        return;
      }
      setLastEventAt(Date.now());
      if (event.type !== "realtime.connected") {
        pushEvent(formatEventLine(event, t));
      }

      applySyncEvent(qc, event);
    },
    [qc, pushEvent, t]
  );

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setStatus((s) => (s === "connected" ? "connected" : "connecting"));
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      backoffRef.current = 1000;
      setStatus("connected");
      setOfflineSince(null);
    };

    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") handleMessage(ev.data);
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      setStatus("reconnecting");
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      reconnectTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [handleMessage]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  useEffect(() => {
    if (status === "connected") {
      setOfflineSince(null);
      return;
    }
    if (status === "offline" && offlineSince == null) {
      setOfflineSince(Date.now());
    }
    if (status !== "offline") {
      const tmr = setTimeout(() => {
        if (mountedRef.current && status === "reconnecting") {
          setStatus("offline");
        }
      }, OFFLINE_BANNER_MS);
      return () => clearTimeout(tmr);
    }
  }, [status, offlineSince]);

  const value = useMemo<RealtimeContextValue>(
    () => ({ status, lastEventAt, recentEvents, pushEvent }),
    [status, lastEventAt, recentEvents, pushEvent]
  );

  const showBanner =
    showOfflineBanner &&
    status === "offline" &&
    offlineSince != null &&
    Date.now() - offlineSince >= OFFLINE_BANNER_MS;

  return (
    <RealtimeContext.Provider value={value}>
      {showBanner && (
        <div className="bg-amber-900/40 border-b border-amber-700/50 px-4 py-2 text-sm text-amber-100 flex justify-between items-center gap-4">
          <span>{t("realtime.offlineBanner")}</span>
          <button
            type="button"
            className="text-amber-200/80 hover:text-amber-50 text-xs shrink-0"
            onClick={() => setShowOfflineBanner(false)}
          >
            ×
          </button>
        </div>
      )}
      {children}
    </RealtimeContext.Provider>
  );
}
