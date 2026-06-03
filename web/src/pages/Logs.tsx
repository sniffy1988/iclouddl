import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { formatDateTime } from "../utils/formatDateTime";
import { useToast } from "../components/ToastProvider";

const LEVELS = ["", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;

function levelClass(level: string) {
  switch (level) {
    case "ERROR":
    case "CRITICAL":
      return "bg-red-900/50 text-red-400";
    case "WARNING":
      return "bg-amber-900/50 text-amber-400";
    case "DEBUG":
      return "bg-violet-900/50 text-violet-400";
    case "INFO":
      return "bg-sky-900/50 text-sky-400";
    default:
      return "bg-slate-800 text-slate-400";
  }
}

export default function Logs() {
  const { t } = useTranslation();
  const toast = useToast();
  const qc = useQueryClient();
  const [level, setLevel] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");

  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["logs", level, appliedSearch],
    queryFn: () =>
      api.logs({
        limit: 200,
        level: level || undefined,
        search: appliedSearch || undefined,
      }),
    refetchInterval:
      settings?.logging_level && settings.logging_level !== "OFF" ? 5000 : false,
  });

  const clear = useMutation({
    mutationFn: api.clearLogs,
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["logs"] });
      toast.success(t("logs.cleared", { count: res.deleted }));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (isLoading) return <div>{t("common.loading")}</div>;

  const activeLogLevel =
    settings?.logging_level ?? (settings?.debug_logging_enabled ? "DEBUG" : "OFF");
  const loggingOff = activeLogLevel === "OFF";

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">{t("logs.title")}</h2>
      <p className="text-slate-500 text-sm mb-4">{t("logs.intro")}</p>

      {loggingOff && (
        <p className="text-amber-400/90 text-sm mb-4 bg-amber-950/40 border border-amber-900/50 rounded-lg px-4 py-3">
          {t("logs.disabledHint")}{" "}
          <Link to="/settings" className="text-sky-400 hover:underline">
            {t("nav.settings")}
          </Link>
        </p>
      )}

      <div className="flex flex-wrap gap-3 mb-6 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">{t("logs.filterLevel")}</label>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
          >
            {LEVELS.map((l) => (
              <option key={l || "all"} value={l}>
                {l || t("logs.allLevels")}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-slate-500 mb-1">{t("logs.search")}</label>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setAppliedSearch(search.trim());
            }}
            placeholder={t("logs.searchPlaceholder")}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={() => setAppliedSearch(search.trim())}
          className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
        >
          {t("logs.applyFilters")}
        </button>
        <button
          type="button"
          disabled={clear.isPending}
          onClick={() => {
            if (window.confirm(t("logs.clearConfirm"))) clear.mutate();
          }}
          className="bg-red-900/60 hover:bg-red-800/80 disabled:opacity-50 px-4 py-2 rounded-lg text-sm text-red-200"
        >
          {clear.isPending ? t("common.loading") : t("logs.clear")}
        </button>
      </div>

      <p className="text-slate-500 text-xs mb-3">
        {t("logs.total", { count: data?.total ?? 0 })}
        {isFetching && !isLoading ? ` · ${t("logs.refreshing")}` : ""}
      </p>

      <div className="space-y-2 font-mono text-xs max-h-[70vh] overflow-y-auto">
        {data?.items.map((entry) => (
          <div
            key={entry.id}
            className="bg-slate-900/80 border border-slate-800 rounded-lg px-3 py-2"
          >
            <div className="flex flex-wrap items-center gap-2 mb-1 text-slate-500">
              <span>{entry.created_at ? formatDateTime(entry.created_at) : "—"}</span>
              <span className={`px-1.5 py-0.5 rounded ${levelClass(entry.level)}`}>
                {entry.level}
              </span>
              <span className="text-slate-600">[{entry.source}]</span>
              <span className="text-slate-600 truncate max-w-[240px]" title={entry.logger_name}>
                {entry.logger_name}
              </span>
            </div>
            <pre className="whitespace-pre-wrap break-words text-slate-300">{entry.message}</pre>
            {entry.exception && (
              <pre className="mt-2 text-red-400/90 whitespace-pre-wrap break-words text-[11px]">
                {entry.exception}
              </pre>
            )}
          </div>
        ))}
      </div>

      {data?.items.length === 0 && (
        <p className="text-slate-500 mt-4">{t("logs.empty")}</p>
      )}
    </div>
  );
}
