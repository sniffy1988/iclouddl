import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, User } from "../api/client";
import AuthorizeButton from "../components/AuthorizeButton";
import { format2faDaysLeft } from "../utils/format2fa";
import FetchCountButton from "../components/FetchCountButton";
import StatusPill from "../components/StatusPill";
import SyncNowButton from "../components/SyncNowButton";
import { formatSyncInterval } from "../utils/syncSchedule";

export default function Users() {
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
  const [fetchOnCreate, setFetchOnCreate] = useState(true);

  const create = useMutation({
    mutationFn: () => api.createUser({ apple_id: appleId }, fetchOnCreate),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowAdd(false);
      setAppleId("");
    },
  });

  const fetchAll = useMutation({
    mutationFn: () => api.fetchAllPhotoCounts(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <h2 className="text-2xl font-semibold">Users</h2>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => fetchAll.mutate()}
            disabled={fetchAll.isPending || !users?.length}
            className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
          >
            {fetchAll.isPending ? "Starting…" : "Fetch all counts"}
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="bg-sky-600 hover:bg-sky-500 px-4 py-2 rounded-lg text-sm"
          >
            Add user
          </button>
        </div>
      </div>

      <p className="text-slate-500 text-sm mb-6">
        Authorize signs in to iCloud (password + 2FA). Fetch count scans iCloud and saves photo
        metadata to the database (slow for large libraries, no download). Sync now downloads
        files.
      </p>

      {showAdd && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-6 space-y-3">
          <div className="flex gap-3">
            <input
              value={appleId}
              onChange={(e) => setAppleId(e.target.value)}
              placeholder="apple@icloud.com"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <button
              onClick={() => create.mutate()}
              disabled={!appleId || create.isPending}
              className="bg-sky-600 px-4 py-2 rounded-lg text-sm"
            >
              {create.isPending ? "Adding…" : "Create"}
            </button>
            <button onClick={() => setShowAdd(false)} className="text-slate-500 px-2">
              Cancel
            </button>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input
              type="checkbox"
              checked={fetchOnCreate}
              onChange={(e) => setFetchOnCreate(e.target.checked)}
              className="rounded"
            />
            Fetch iCloud photo count after adding (no download)
          </label>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead>
            <tr className="text-slate-500 border-b border-slate-800">
              <th className="text-left py-2 pr-4">Apple ID</th>
              <th className="text-left py-2 pr-4">Auth</th>
              <th className="text-left py-2 pr-4">Activity</th>
              <th className="text-left py-2 pr-4">2FA left</th>
              <th className="text-right py-2 pr-4">iCloud photos</th>
              <th className="text-right py-2 pr-4">Downloaded</th>
              <th className="text-right py-2 pr-4">Remaining</th>
              <th className="text-left py-2 pr-4">Schedule</th>
              <th className="text-left py-2 pr-4">Last sync</th>
              <th className="text-left py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b border-slate-800/50 hover:bg-slate-900/50">
                <td className="py-3 pr-4">
                  <Link
                    to={`/users/${u.id}`}
                    className="text-sky-400 hover:underline font-medium"
                    title="Manage user"
                  >
                    {u.apple_id}
                  </Link>
                  {!u.enabled && (
                    <span className="ml-2 text-xs text-slate-500">(disabled)</span>
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
                    <span className="text-sky-400" title="Indexing iCloud library into database">
                      {(u.icloud_photos_count ?? 0).toLocaleString()}
                    </span>
                  ) : (
                    (u.icloud_photos_count?.toLocaleString() ?? "—")
                  )}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums text-slate-300">
                  {u.downloaded_count?.toLocaleString() ?? 0}
                </td>
                <td className="py-3 pr-4 text-right tabular-nums text-slate-400">
                  {u.activity_status === "counting" ? (
                    <span className="text-slate-500" title="Available after indexing finishes">
                      …
                    </span>
                  ) : u.remaining_to_download != null ? (
                    u.remaining_to_download.toLocaleString()
                  ) : (
                    "—"
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-500 text-xs whitespace-nowrap">
                  {u.enabled ? (
                    <>
                      <span className="text-slate-400">{formatSyncInterval(u.sync_interval_seconds)}</span>
                      <br />
                      {u.next_sync_at ? (
                        <span title="Next scheduled sync">
                          Next {new Date(u.next_sync_at).toLocaleString()}
                        </span>
                      ) : (
                        "—"
                      )}
                    </>
                  ) : (
                    <span className="text-amber-500/80">Off</span>
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-500 whitespace-nowrap">
                  {u.last_sync_at ? new Date(u.last_sync_at).toLocaleString() : "—"}
                </td>
                <td className="py-3">
                  <div className="flex flex-wrap gap-2">
                    <AuthorizeButton
                      userId={u.id}
                      appleId={u.apple_id}
                      icloudAuthorized={u.icloud_authorized}
                      icloudNeedsAuth={u.icloud_needs_auth}
                      size="sm"
                    />
                    <FetchCountButton userId={u.id} disabled={!u.enabled} size="sm" />
                    <SyncNowButton
                      userId={u.id}
                      appleId={u.apple_id}
                      disabled={!u.enabled}
                      size="sm"
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {users?.length === 0 && (
        <p className="text-slate-500 mt-6">
          No users yet. Add an Apple ID above — you can fetch the photo count before syncing.
        </p>
      )}
    </div>
  );
}
