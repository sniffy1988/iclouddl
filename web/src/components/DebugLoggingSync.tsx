import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../api/client";
import { setDebugLoggingEnabled } from "../utils/debugLog";

/** Mirrors server debug_logging_enabled into browser console helpers. */
export default function DebugLoggingSync() {
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
    staleTime: 30_000,
  });

  useEffect(() => {
    setDebugLoggingEnabled(Boolean(settings?.debug_logging_enabled));
  }, [settings?.debug_logging_enabled]);

  return null;
}
