import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, User } from "../api/client";
import AuthorizeButton from "../components/AuthorizeButton";
import { format2faDaysLeft } from "../utils/format2fa";
import StatusPill from "../components/StatusPill";
import { formatSyncInterval } from "../utils/syncSchedule";
import { useToast } from "../components/ToastProvider";

export default function Users() {
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
      toast.success(`User ${user.account_label || user.id} added`);
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
        Each user can link iCloud and/or Google Photos. Use per-provider Count and Sync on the user
        detail page. For dual-source downloads, set path template to include {"{source}"} (e.g.{" "}
        {"{source}/YYYY/MM/DD/{filename}"}).
      </p>

      {showAdd && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 mb-6 space-y-3">
          <p className="text-xs text-slate-500">
            Provide a display name and/or Apple ID. Google Photos can be linked later on the user
            page. At least one label is required.
          </p>
          <div className="flex flex-wrap gap-3">
            <input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Display name (optional)"
              className="flex-1 min-w-[140px] bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <input
              value={appleId}
              onChange={(e) => setAppleId(e.target.value)}
              placeholder="Apple ID (optional)"
              className="flex-1 min-w-[180px] bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <button
              onClick={() => create.mutate()}
              disabled={(!appleId.trim() && !displayName.trim()) || create.isPending}
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
              <th className="text-left py-2 pr-4">User</th>
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
                    {u.account_label || u.apple_id || u.google_account_email || `#${u.id}`}
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
                    {u.apple_id && (
                      <AuthorizeButton
                        userId={u.id}
                        appleId={u.apple_id}
                        icloudAuthorized={u.icloud_authorized}
                        icloudNeedsAuth={u.icloud_needs_auth}
                        size="sm"
                      />
                    )}
                    <Link
                      to={`/users/${u.id}`}
                      className="text-sky-400 hover:underline text-xs px-2 py-1"
                    >
                      Manage
                    </Link>
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
