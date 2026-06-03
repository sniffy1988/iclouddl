import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, User } from "../api/client";
import { format2faDaysLeft } from "../utils/format2fa";
import StatusPill from "../components/StatusPill";
import { formatSyncInterval } from "../utils/syncSchedule";
import { useToast } from "../components/ToastProvider";

export default function Users() {
  const { t } = useTranslation();
  const toast = useToast();
  const qc = useQueryClient();
  const hasCounting = (users: User[] | undefined) =>
    users?.some((u) => u.activity_status === "counting") ?? false;
  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: api.users,
    refetchInterval: (q) => (hasCounting(q.state.data) ? 3000 : 10000),
  });

  const [showAdd, setShowAdd] = useState(false);
  const [appleId, setAppleId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [fetchOnCreate, setFetchOnCreate] = useState(true);

  const create = useMutation({
    mutationFn: () =>
      api.createUser(
        {
          apple_id: appleId.trim() || undefined,
          display_name: displayName.trim() || undefined,
        },
        fetchOnCreate && !!appleId.trim()
      ),
    onSuccess: (user) => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowAdd(false);
      setAppleId("");
      setDisplayName("");
      toast.success(
        t("users.userAdded", { label: user.account_label || user.id })
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const fetchAll = useMutation({
    mutationFn: () => api.fetchAllPhotoCounts(),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.info(r.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (isLoading) return <div>{t("common.loading")}</div>;

  return (
    <div>
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <h2 className="text-2xl font-semibold">{t("users.title")}</h2>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => fetchAll.mutate()}
            disabled={fetchAll.isPending || !users?.length}
            className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
          >
            {fetchAll.isPending ? t("common.starting") : t("users.fetchAllCounts")}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="bg-sky-600 hover:bg-sky-500 px-4 py-2 rounded-lg text-sm"
          >
            {t("users.addUser")}
          </button>
        </div>
      </div>

      <p className="text-slate-500 text-sm mb-6">{t("users.intro")}</p>

      {showAdd && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-6 space-y-3">
          <p className="text-xs text-slate-500">{t("users.addHint")}</p>
          <div className="flex flex-wrap gap-3">
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("users.displayNamePlaceholder")}
              className="flex-1 min-w-[140px] bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <input
              value={appleId}
              onChange={(e) => setAppleId(e.target.value)}
              placeholder={t("users.appleIdPlaceholder")}
              className="flex-1 min-w-[180px] bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <button
              onClick={() => create.mutate()}
              disabled={(!appleId.trim() && !displayName.trim()) || create.isPending}
              className="bg-sky-600 px-4 py-2 rounded-lg text-sm"
            >
              {create.isPending ? t("common.adding") : t("common.create")}
            </button>
            <button onClick={() => setShowAdd(false)} className="text-slate-500 px-2">
              {t("common.cancel")}
            </button>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={fetchOnCreate}
              onChange={(e) => setFetchOnCreate(e.target.checked)}
              className="rounded"
            />
            {t("users.fetchOnCreate")}
          </label>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="text-left py-2 pr-4">{t("users.colUser")}</th>
              <th className="text-left py-2 pr-4">{t("users.colAuth")}</th>
              <th className="text-left py-2 pr-4">{t("users.colActivity")}</th>
              <th className="text-left py-2 pr-4">{t("users.col2fa")}</th>
              <th className="text-right py-2 pr-4">{t("users.colIcloudPhotos")}</th>
              <th className="text-right py-2 pr-4">{t("users.colDownloaded")}</th>
              <th className="text-right py-2 pr-4">{t("users.colRemaining")}</th>
              <th className="text-left py-2 pr-4">{t("users.colSchedule")}</th>
              <th className="text-left py-2 pr-4">{t("users.colLastSync")}</th>
              <th className="text-left py-2">{t("users.colActions")}</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b border-slate-800/50 hover:bg-slate-900/50">
                <td className="py-3 pr-4">
                  <Link
                    to={`/users/${u.id}`}
                    className="text-sky-400 hover:underline font-medium"
                    title={t("users.manageUserTitle")}
                  >
                    {u.account_label || u.apple_id || u.google_account_email || `#${u.id}`}
                  </Link>
                  {!u.enabled && (
                    <span className="ml-2 text-xs text-slate-500">{t("common.disabled")}</span>
                  )}
                </td>
                <td className="py-3 pr-4">
                  <StatusPill variant="auth" status={u.auth_status} />
                </td>
                <td className="py-3 pr-4">
                  <StatusPill variant="activity" status={u.activity_status} />
                </td>
                <td className="py-3 pr-4 text-slate-400 whitespace-nowrap text-xs">
                  {format2faDaysLeft(u.days_until_2fa_expires)}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums">
                  {u.activity_status === "counting" ? (
                    <span className="text-sky-400" title={t("users.indexingTitle")}>
                      {(u.icloud_photos_count ?? 0).toLocaleString()}
                    </span>
                  ) : (
                    (u.icloud_photos_count?.toLocaleString() ?? t("common.dash"))
                  )}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums text-slate-300">
                  {u.downloaded_count?.toLocaleString() ?? 0}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums text-slate-400">
                  {u.activity_status === "counting" ? (
                    <span className="text-slate-500" title={t("users.remainingAfterIndex")}>
                      …
                    </span>
                  ) : u.remaining_to_download != null ? (
                    u.remaining_to_download.toLocaleString()
                  ) : (
                    t("common.dash")
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-500 text-xs whitespace-nowrap">
                  {u.enabled ? (
                    <>
                      <span className="text-slate-400">{formatSyncInterval(u.sync_interval_seconds)}</span>
                      <br />
                      {u.next_sync_at ? (
                        <span title={t("common.nextScheduledSync")}>
                          {t("common.next", {
                            time: new Date(u.next_sync_at).toLocaleString(),
                          })}
                        </span>
                      ) : (
                        t("common.dash")
                      )}
                    </>
                  ) : (
                    <span className="text-amber-500/80">{t("common.off")}</span>
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-500 whitespace-nowrap">
                  {u.last_sync_at ? new Date(u.last_sync_at).toLocaleString() : t("common.dash")}
                </td>
                <td className="py-3">
                  <Link
                    to={`/users/${u.id}`}
                    className="text-sky-400 hover:underline text-xs px-2 py-1"
                  >
                    {t("common.manage")}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {users?.length === 0 && (
        <p className="text-slate-500 mt-6">{t("users.empty")}</p>
      )}
    </div>
  );
}
