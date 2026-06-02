import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../components/ToastProvider";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <p className="text-slate-500 text-sm">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: stats, refetch } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: 15000,
  });
  const [events, setEvents] = useState<string[]>([]);
  const toast = useToast();

  const triggerDue = useMutation({
    mutationFn: () => api.triggerDueSyncs(),
    onSuccess: (r) => {
      toast.success(r.message);
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["sync-runs"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  useEffect(() => {
    const es = new EventSource("/api/events/sync", { withCredentials: true });
    const onEvent = (e: MessageEvent) => {
      try {
        const d = JSON.parse(e.data);
        setEvents((prev) => [`${d.type} ${d.apple_id || ""}`, ...prev].slice(0, 20));
        if (d.type?.startsWith("sync.") || d.type?.startsWith("count.")) {
          refetch();
          qc.invalidateQueries({ queryKey: ["users"] });
          qc.invalidateQueries({ queryKey: ["sync-runs"] });
        }
      } catch {
        /* ignore */
      }
    };
    es.addEventListener("message", onEvent);
    es.onmessage = onEvent;
    return () => es.close();
  }, [refetch, qc]);

  if (!stats) return <div>{t("common.loading")}</div>;

  return (
    <div>
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <h2 className="text-2xl font-semibold">{t("dashboard.title")}</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() => triggerDue.mutate()}
            disabled={triggerDue.isPending || stats.users_due_for_sync === 0}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
          >
            {triggerDue.isPending
              ? t("common.starting")
              : t("dashboard.syncAllDue", { count: stats.users_due_for_sync })}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label={t("dashboard.totalUsers")} value={stats.total_users} />
        <StatCard label={t("dashboard.enabledUsers")} value={stats.enabled_users} />
        <StatCard label={t("dashboard.photosDownloaded")} value={stats.total_photos} />
        <StatCard label={t("dashboard.downloadedToday")} value={stats.downloaded_today} />
        <StatCard label={t("dashboard.activeSyncs")} value={stats.active_syncs} />
        <StatCard label={t("dashboard.failedSyncs")} value={stats.failed_syncs} />
        <StatCard label={t("dashboard.dueForSync")} value={stats.users_due_for_sync} />
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-medium mb-3">{t("dashboard.liveEvents")}</h3>
          <ul className="text-sm text-slate-400 space-y-1 max-h-64 overflow-auto">
            {events.length === 0 && <li>{t("dashboard.noEvents")}</li>}
            {events.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-medium mb-3">{t("dashboard.quickLinks")}</h3>
          <Link to="/users" className="text-sky-400 hover:underline block">
            {t("dashboard.manageUsersLink")}
          </Link>
          <Link to="/sync-runs" className="text-sky-400 hover:underline block mt-2">
            {t("dashboard.syncHistoryLink")}
          </Link>
        </div>
      </div>
    </div>
  );
}
