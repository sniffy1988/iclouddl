import { useTranslation } from "react-i18next";
import { useRealtime } from "../hooks/useRealtime";

export default function RealtimeIndicator() {
  const { t } = useTranslation();
  const { status, lastEventAt } = useRealtime();

  const config = {
    connected: { dot: "bg-emerald-400", label: "realtime.connected" as const },
    connecting: { dot: "bg-amber-400 animate-pulse", label: "realtime.reconnecting" as const },
    reconnecting: { dot: "bg-amber-400 animate-pulse", label: "realtime.reconnecting" as const },
    offline: { dot: "bg-slate-500", label: "realtime.offline" as const },
  }[status];

  const tooltip =
    status === "connected" && lastEventAt
      ? new Date(lastEventAt).toLocaleTimeString()
      : status === "offline"
        ? t("realtime.offlineTooltip")
        : undefined;

  return (
    <div
      className="flex items-center gap-2 text-xs text-slate-400 mb-3"
      title={tooltip}
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${config.dot}`} />
      <span>{t(config.label)}</span>
    </div>
  );
}
