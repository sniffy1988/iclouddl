import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { formatDateTime } from "../utils/formatDateTime";
import StopSyncButton from "../components/StopSyncButton";
import SyncNowButton from "../components/SyncNowButton";

export default function SyncRuns() {
  const { t } = useTranslation();
  const { data: runs, isLoading } = useQuery({
    queryKey: ["sync-runs"],
    queryFn: () => api.syncRuns({ limit: 100 }),
    refetchInterval: 10000,
  });

  if (isLoading) return <div>{t("common.loading")}</div>;

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-2">{t("syncRuns.title")}</h2>
      <p className="text-slate-500 text-sm mb-6">{t("syncRuns.intro")}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2">{t("syncRuns.colId")}</th>
            <th className="text-left py-2">{t("syncRuns.colUser")}</th>
            <th className="text-left py-2">{t("syncRuns.colStatus")}</th>
            <th className="text-left py-2">{t("syncRuns.colDownloaded")}</th>
            <th className="text-left py-2">{t("syncRuns.colFailed")}</th>
            <th className="text-left py-2">{t("syncRuns.colStarted")}</th>
            <th className="text-left py-2">{t("syncRuns.colError")}</th>
            <th className="text-left py-2">{t("syncRuns.colActions")}</th>
          </tr>
        </thead>
        <tbody>
          {runs?.map((r) => (
            <tr key={r.id} className="border-b border-slate-800/50">
              <td className="py-3">{r.id}</td>
              <td className="py-3">
                <Link to={`/users/${r.user_id}`} className="text-sky-400 hover:underline">
                  {t("common.userNumber", { id: r.user_id })}
                </Link>
              </td>
              <td className="py-3">
                <span
                  className={`px-2 py-0.5 rounded text-xs capitalize ${
                    r.status === "completed"
                      ? "bg-green-900/50 text-green-400"
                      : r.status === "failed"
                        ? "bg-red-900/50 text-red-400"
                        : r.status === "running"
                          ? "bg-sky-900/50 text-sky-400"
                          : "bg-slate-800"
                  }`}
                >
                  {t(`syncRunStatus.${r.status}`, { defaultValue: r.status })}
                </span>
              </td>
              <td className="py-3">{r.photos_downloaded}</td>
              <td className="py-3">{r.photos_failed}</td>
              <td className="py-3 text-slate-500">
                {formatDateTime(r.started_at)}
              </td>
              <td className="py-3 text-slate-500 text-xs max-w-[200px] truncate">
                {r.error_summary || t("common.dash")}
              </td>
              <td className="py-3">
                <div className="flex flex-wrap gap-2">
                  {r.status === "running" && (
                    <StopSyncButton
                      userId={r.user_id}
                      source={
                        r.scope === "icloud" || r.scope === "google_photos"
                          ? r.scope
                          : undefined
                      }
                      size="sm"
                    />
                  )}
                  {r.status !== "running" && (
                    <SyncNowButton userId={r.user_id} size="sm" />
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {runs?.length === 0 && <p className="text-slate-500 mt-4">{t("syncRuns.empty")}</p>}
    </div>
  );
}
