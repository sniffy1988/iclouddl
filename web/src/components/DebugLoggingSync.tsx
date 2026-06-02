import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../api/client";
import { setDebugLoggingEnabled } from "../utils/debugLog";
import { browserConsoleDebugEnabled } from "../utils/loggingLevel";

/** Mirrors server logging level into browser console helpers (DEBUG only). */
export default function DebugLoggingSync() {
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
    staleTime: 30_000,
  });

  useEffect(() => {
    const level = settings?.logging_level ?? (settings?.debug_logging_enabled ? "DEBUG" : "OFF");
    setDebugLoggingEnabled(browserConsoleDebugEnabled(level));
  }, [settings?.logging_level, settings?.debug_logging_enabled]);

  return null;
}
