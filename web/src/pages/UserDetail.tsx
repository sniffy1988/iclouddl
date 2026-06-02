import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import AuthorizeButton from "../components/AuthorizeButton";
import { format2faDaysLeft } from "../utils/format2fa";
import StatusPill from "../components/StatusPill";
import FetchCountButton from "../components/FetchCountButton";
import SyncNowButton from "../components/SyncNowButton";

export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const qc = useQueryClient();

  const { data: user } = useQuery({
    queryKey: ["user", userId],
    queryFn: () => api.getUser(userId),
    enabled: !!userId,
    refetchInterval: (q) => {
      const activity = q.state.data?.activity_status;
      return activity === "queued" || activity === "syncing" || activity === "counting"
        ? 3000
        : false;
    },
  });

  const { data: counts } = useQuery({
    queryKey: ["photo-counts", userId],
    queryFn: () => api.photoCounts(userId),
    enabled: !!userId,
    refetchInterval: user?.activity_status === "counting" ? 3000 : false,
  });
  const { data: photos } = useQuery({
    queryKey: ["photos", userId],
    queryFn: () => api.photos(userId),
    enabled: !!userId,
  });
  const { data: syncRuns } = useQuery({
    queryKey: ["sync-runs", userId],
    queryFn: () => api.syncRuns({ user_id: userId, limit: 10 }),
    enabled: !!userId,
    refetchInterval:
      user?.activity_status === "syncing" || user?.activity_status === "queued" ? 3000 : false,
  });

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.updateUser(userId, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user", userId] }),
  });

  if (!user) return <div>Loading...</div>;

  const isActive =
    user.activity_status === "queued" ||
    user.activity_status === "syncing" ||
    user.activity_status === "counting";

  const isCounting = user?.activity_status === "counting";
  const remaining = isCounting ? null : counts?.remaining_to_download ?? null;

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <Link to="/users" className="text-slate-500 hover:text-slate-300 text-sm">
          ← Users
        </Link>
      </div>
      <h2 className="text-2xl font-semibold mb-2">{user.apple_id}</h2>
      <p className="text-slate-500 mb-4">{user.display_name}</p>

      {isActive && (
        <div className="bg-sky-900/30 border border-sky-700 rounded-xl p-4 mb-6 flex items-center gap-3">
          <span className="inline-block w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
          <span className="text-sky-300 text-sm">
            {user.activity_status === "counting"
              ? "Indexing photos from iCloud…"
              : "Sync in progress — this page refreshes automatically"}
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <StatusPill variant="auth" status={user.auth_status} />
        <StatusPill variant="activity" status={user.activity_status} />
        {user.icloud_2fa_at && (
          <span className="text-slate-500 text-sm whitespace-nowrap">
            2FA left: {format2faDaysLeft(user.days_until_2fa_expires)}
          </span>
        )}
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">iCloud photos</p>
          <p className="text-2xl font-semibold mt-1">
            {isCounting
              ? (user.icloud_photos_count ?? 0).toLocaleString()
              : (user.icloud_photos_count ?? "—")}
          </p>
          {isCounting && (
            <p className="text-xs text-sky-400 mt-1">Indexing iCloud library…</p>
          )}
          {user.icloud_photos_count_at && (
            <p className="text-xs text-slate-500 mt-1">
              {new Date(user.icloud_photos_count_at).toLocaleString()}
            </p>
          )}
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Downloaded locally</p>
          <p className="text-2xl font-semibold mt-1">
            {counts?.downloaded_count ?? "—"}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Remaining to download</p>
          <p className="text-2xl font-semibold mt-1">
            {isCounting ? "…" : (remaining ?? "—")}
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Last sync</p>
          <p className="mt-1 text-sm">
            {user.last_sync_at ? new Date(user.last_sync_at).toLocaleString() : "—"}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Next scheduled</p>
          <p className="mt-1 text-sm">
            {user.next_sync_at ? new Date(user.next_sync_at).toLocaleString() : "—"}
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Download dir</p>
          <p className="font-mono text-sm mt-1 break-all">{user.download_dir}</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Sync interval</p>
          <p className="mt-1">{Math.round(user.sync_interval_seconds / 3600)} hours</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-8 items-center">
        <AuthorizeButton
          userId={userId}
          appleId={user.apple_id}
          icloudAuthorized={user.icloud_authorized}
          icloudNeedsAuth={user.icloud_needs_auth}
        />
        <FetchCountButton userId={userId} disabled={!user.enabled} />
        <SyncNowButton
          userId={userId}
          appleId={user.apple_id}
          disabled={!user.enabled}
        />
        <button
          onClick={() => toggle.mutate(!user.enabled)}
          className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
        >
          {user.enabled ? "Disable user" : "Enable user"}
        </button>
        {!user.enabled && (
          <span className="text-slate-500 text-sm">Enable user to run sync</span>
        )}
      </div>

      <h3 className="font-medium mb-3">Recent sync runs</h3>
      <table className="w-full text-sm mb-8">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2">Run</th>
            <th className="text-left py-2">Status</th>
            <th className="text-left py-2">Downloaded</th>
            <th className="text-left py-2">Failed</th>
            <th className="text-left py-2">Started</th>
            <th className="text-left py-2"></th>
          </tr>
        </thead>
        <tbody>
          {syncRuns?.map((r) => (
            <tr key={r.id} className="border-b border-slate-800/50">
              <td className="py-2">#{r.id}</td>
              <td className="py-2 capitalize">{r.status}</td>
              <td className="py-2">{r.photos_downloaded}</td>
              <td className="py-2">{r.photos_failed}</td>
              <td className="py-2 text-slate-500">
                {new Date(r.started_at).toLocaleString()}
              </td>
              <td className="py-2">
                {(r.status === "failed" || r.status === "completed") && (
                  <SyncNowButton userId={userId} size="sm" />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {(!syncRuns || syncRuns.length === 0) && (
        <p className="text-slate-500 text-sm mb-8">No sync runs yet — use Sync now to start.</p>
      )}

      <h3 className="font-medium mb-3">Recent photos ({photos?.length ?? 0})</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2">Filename</th>
            <th className="text-left py-2">Status</th>
            <th className="text-left py-2">Size</th>
          </tr>
        </thead>
        <tbody>
          {photos?.slice(0, 20).map((p) => (
            <tr key={p.id} className="border-b border-slate-800/50">
              <td className="py-2">{p.filename}</td>
              <td className="py-2">{p.status}</td>
              <td className="py-2 text-slate-500">
                {p.file_size ? `${(p.file_size / 1024).toFixed(0)} KB` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
