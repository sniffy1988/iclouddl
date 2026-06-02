import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../components/ToastProvider";
import AuthorizeButton from "../components/AuthorizeButton";
import { format2faDaysLeft } from "../utils/format2fa";
import StatusPill from "../components/StatusPill";
import ConnectGoogleButton from "../components/ConnectGoogleButton";
import FieldHelp, { HelpBox } from "../components/FieldHelp";
import FetchCountButton from "../components/FetchCountButton";
import SyncNowButton from "../components/SyncNowButton";
import {
  SYNC_INTERVAL_PRESETS,
  formatSyncInterval,
  hoursToSeconds,
  presetForSeconds,
  secondsToHours,
} from "../utils/syncSchedule";

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <h3 className="font-medium text-slate-200">{title}</h3>
      {description && <p className="text-slate-500 text-sm mt-1 mb-4">{description}</p>}
      {!description && <div className="mb-4" />}
      {children}
    </section>
  );
}

export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: user } = useQuery({
    queryKey: ["user", userId],
    queryFn: () => api.getUser(userId),
    enabled: !!userId,
    refetchInterval: (q) => {
      const activity = q.state.data?.activity_status;
      return (
        activity === "queued" ||
        activity === "syncing" ||
        activity === "counting" ||
        activity === "counting_icloud" ||
        activity === "counting_google"
      )
        ? 3000
        : false;
    },
  });

  const { data: counts } = useQuery({
    queryKey: ["photo-counts", userId],
    queryFn: () => api.photoCounts(userId),
    enabled: !!userId,
    refetchInterval:
      user?.activity_status === "counting" ||
      user?.activity_status === "counting_icloud" ||
      user?.activity_status === "counting_google"
        ? 3000
        : false,
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

  const [displayName, setDisplayName] = useState("");
  const [appleIdEdit, setAppleIdEdit] = useState("");
  const [downloadDir, setDownloadDir] = useState("");
  const [intervalPreset, setIntervalPreset] = useState("21600");
  const [customHours, setCustomHours] = useState("6");
  const [scheduledEnabled, setScheduledEnabled] = useState(true);
  const [immichLibraryId, setImmichLibraryId] = useState("");
  const [immichScanAfterSync, setImmichScanAfterSync] = useState(false);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name ?? "");
    setAppleIdEdit(user.apple_id ?? "");
    setDownloadDir(user.download_dir);
    setIntervalPreset(presetForSeconds(user.sync_interval_seconds));
    setCustomHours(String(secondsToHours(user.sync_interval_seconds)));
    setScheduledEnabled(user.enabled);
    setImmichLibraryId(user.immich_library_id ?? "");
    setImmichScanAfterSync(user.immich_scan_after_sync);
  }, [user]);

  const toast = useToast();

  useEffect(() => {
    if (searchParams.get("google") === "connected") {
      toast.success("Google Photos connected");
      qc.invalidateQueries({ queryKey: ["user", userId] });
      searchParams.delete("google");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, toast, qc, userId]);

  const testImmich = useMutation({
    mutationFn: () => api.testUserImmich(userId),
    onSuccess: (data) => {
      if (data.ok) toast.success(data.message);
      else toast.error(data.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const immichLibraries = useQuery({
    queryKey: ["immich-libraries"],
    queryFn: api.immichLibraries,
    enabled: immichScanAfterSync,
    retry: false,
  });

  const saveSettings = useMutation({
    mutationFn: (opts?: { reschedule_sync?: boolean }) => {
      const seconds =
        intervalPreset === "custom"
          ? hoursToSeconds(parseFloat(customHours) || 6)
          : Number(intervalPreset);
      return api.updateUser(userId, {
        display_name: displayName.trim() || user!.account_label || user!.apple_id || "User",
        apple_id: appleIdEdit.trim() || undefined,
        download_dir: downloadDir.trim(),
        sync_interval_seconds: seconds,
        enabled: scheduledEnabled,
        immich_library_id: immichScanAfterSync ? immichLibraryId.trim() || null : null,
        immich_scan_after_sync: immichScanAfterSync,
        reschedule_sync: opts?.reschedule_sync,
      });
    },
    onSuccess: () => {
      toast.success("User settings saved");
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (!user) return <div>Loading...</div>;

  const isActive =
    user.activity_status === "queued" ||
    user.activity_status === "syncing" ||
    user.activity_status === "counting" ||
    user.activity_status === "counting_icloud" ||
    user.activity_status === "counting_google";

  const isCountingIcloud = user.activity_status === "counting_icloud";
  const isCountingGoogle = user.activity_status === "counting_google";
  const syncBusy = user.active_syncs_by_scope ?? {};
  const title = user.account_label || user.display_name || user.apple_id || user.google_account_email || `User #${user.id}`;

  const syncIntervalSeconds =
    intervalPreset === "custom"
      ? hoursToSeconds(parseFloat(customHours) || 6)
      : Number(intervalPreset);

  return (
    <div className="max-w-5xl">
      <div className="flex items-center gap-3 mb-2">
        <Link to="/users" className="text-slate-500 hover:text-slate-300 text-sm">
          ← Users
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="text-slate-500 text-sm mt-1">
            User #{user.id} · iCloud + Google Photos · use {"{source}/"} in path template for dual-source
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill variant="auth" status={user.icloud_auth_status} />
          <StatusPill variant="auth" status={user.google_auth_status} />
          <StatusPill variant="activity" status={user.activity_status} />
        </div>
      </div>

      {isActive && (
        <div className="bg-sky-900/30 border border-sky-700 rounded-xl p-4 mb-6 flex items-center gap-3">
          <span className="inline-block w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
          <span className="text-sky-300 text-sm">
            {user.activity_status === "counting_icloud"
              ? "Indexing iCloud library…"
              : user.activity_status === "counting_google"
                ? "Indexing Google Photos…"
                : user.activity_status === "counting"
                  ? "Indexing photos…"
                  : "Sync in progress — this page refreshes automatically"}
          </span>
        </div>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">iCloud photos</p>
          <p className="text-2xl font-semibold mt-1">
            {isCountingIcloud
              ? (user.icloud_photos_count ?? 0).toLocaleString()
              : (user.icloud_photos_count?.toLocaleString() ?? "—")}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Google photos</p>
          <p className="text-2xl font-semibold mt-1">
            {isCountingGoogle
              ? (user.google_photos_count ?? 0).toLocaleString()
              : (user.google_photos_count?.toLocaleString() ?? "—")}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Downloaded (all)</p>
          <p className="text-2xl font-semibold mt-1">{counts?.downloaded_count ?? 0}</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">Remaining (est.)</p>
          <p className="text-2xl font-semibold mt-1">
            {isCountingIcloud || isCountingGoogle
              ? "…"
              : (counts?.remaining_to_download?.toLocaleString() ?? "—")}
          </p>
        </div>
      </div>

      <div className="space-y-6 mb-8">
        <Section
          title="iCloud"
          description="Authorize with Apple ID, password, and 2FA. Count indexes metadata; Sync downloads files."
        >
          {!user.apple_id && (
            <p className="text-amber-400 text-sm mb-3">
              Set an Apple ID in Storage & profile below to use iCloud.
            </p>
          )}
          <HelpBox title="Before you sign in">
            <ul className="list-disc list-inside space-y-1">
              <li>
                On iPhone/iPad: <strong className="text-slate-300">Settings → Apple ID → iCloud →
                Access iCloud Data on the Web</strong> must be on.
              </li>
              <li>
                <strong className="text-slate-300">Advanced Data Protection</strong> must be off
                (blocks server photo API).
              </li>
              <li>
                Use your Apple ID password; if 2FA is enabled, approve on a trusted device or enter
                the code in Telegram with <span className="font-mono">/code 123456</span> (if
                configured in Settings).
              </li>
            </ul>
          </HelpBox>
          <div className="flex flex-wrap items-center gap-3 mb-3">
            {user.apple_id && (
              <>
                <AuthorizeButton
                  userId={userId}
                  appleId={user.apple_id}
                  icloudAuthorized={user.icloud_authorized}
                  icloudNeedsAuth={user.icloud_needs_auth}
                />
                {user.icloud_2fa_at && (
                  <span className="text-slate-400 text-sm">
                    Trusted session: {format2faDaysLeft(user.days_until_2fa_expires)}
                  </span>
                )}
              </>
            )}
          </div>
          {user.icloud_authenticated_at && (
            <p className="text-xs text-slate-500 mb-3">
              Last sign-in: {new Date(user.icloud_authenticated_at).toLocaleString()}
            </p>
          )}
          <FieldHelp className="mb-3">
            <strong className="text-slate-400">Count iCloud</strong> — scans the library into the
            database (no files). <strong className="text-slate-400">Sync iCloud</strong> — downloads
            pending photos only.
          </FieldHelp>
          <div className="flex flex-wrap gap-2">
            <FetchCountButton
              userId={userId}
              source="icloud"
              disabled={!user.enabled || !user.apple_id || syncBusy.icloud}
            />
            <SyncNowButton
              userId={userId}
              source="icloud"
              disabled={
                !user.enabled ||
                !user.apple_id ||
                !user.icloud_authorized ||
                user.icloud_needs_auth ||
                syncBusy.icloud
              }
            />
          </div>
        </Section>

        <Section
          title="Google Photos"
          description="One-time OAuth per user. App credentials are configured under Settings → Google Photos OAuth."
        >
          <HelpBox title="Setup checklist">
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                In <strong className="text-slate-300">Settings</strong>: Google OAuth client ID +
                secret, and server <span className="font-mono">TOKEN_ENCRYPTION_KEY</span> in .env.
              </li>
              <li>Click <strong className="text-slate-300">Connect Google Photos</strong> below and
                sign in with the Google account that owns the library.</li>
              <li>
                Use <strong className="text-slate-300">Count Google</strong> then{" "}
                <strong className="text-slate-300">Sync Google</strong> (same as iCloud).
              </li>
            </ol>
          </HelpBox>
          {user.google_account_email && (
            <p className="text-sm text-slate-400 mb-2">Connected as {user.google_account_email}</p>
          )}
          <ConnectGoogleButton userId={userId} disabled={!user.enabled} />
          <FieldHelp className="mt-3">
            Opens Google sign-in in a new tab. After approving, you are redirected back to this user
            page. If connect fails, check redirect URI in Google Cloud matches Settings.
          </FieldHelp>
          <div className="flex flex-wrap gap-2 mt-4">
            <FetchCountButton
              userId={userId}
              source="google_photos"
              disabled={!user.enabled || !user.google_authorized || syncBusy.google_photos}
            />
            <SyncNowButton
              userId={userId}
              source="google_photos"
              disabled={
                !user.enabled ||
                !user.google_authorized ||
                user.google_needs_auth ||
                syncBusy.google_photos
              }
            />
          </div>
        </Section>

        <Section
          title="Sync schedule"
          description="The background worker runs a full download on this interval when scheduling is enabled."
        >
          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Interval</label>
              <select
                value={intervalPreset}
                onChange={(e) => setIntervalPreset(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              >
                {SYNC_INTERVAL_PRESETS.map((p) => (
                  <option key={p.seconds} value={String(p.seconds)}>
                    {p.label}
                  </option>
                ))}
                <option value="custom">Custom (hours)</option>
              </select>
            </div>
            {intervalPreset === "custom" && (
              <div>
                <label className="block text-sm text-slate-400 mb-1">Hours between syncs</label>
                <input
                  type="number"
                  min={0.083}
                  step={0.5}
                  value={customHours}
                  onChange={(e) => setCustomHours(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-slate-500 mt-1">Minimum 5 minutes (0.083 h)</p>
              </div>
            )}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-300 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={scheduledEnabled}
              onChange={(e) => setScheduledEnabled(e.target.checked)}
              className="rounded"
            />
            Scheduled sync enabled
          </label>

          <dl className="grid sm:grid-cols-2 gap-3 text-sm mb-4">
            <div className="bg-slate-800/50 rounded-lg px-3 py-2">
              <dt className="text-slate-500">Current interval</dt>
              <dd className="text-slate-200 mt-0.5">{formatSyncInterval(syncIntervalSeconds)}</dd>
            </div>
            <div className="bg-slate-800/50 rounded-lg px-3 py-2">
              <dt className="text-slate-500">Next scheduled sync</dt>
              <dd className="text-slate-200 mt-0.5">
                {scheduledEnabled && user.next_sync_at
                  ? new Date(user.next_sync_at).toLocaleString()
                  : scheduledEnabled
                    ? "Soon"
                    : "— (disabled)"}
              </dd>
            </div>
            <div className="bg-slate-800/50 rounded-lg px-3 py-2">
              <dt className="text-slate-500">Last sync</dt>
              <dd className="text-slate-200 mt-0.5">
                {user.last_sync_at ? new Date(user.last_sync_at).toLocaleString() : "—"}
              </dd>
            </div>
          </dl>
        </Section>

        <Section
          title="Storage & profile"
          description="Photos are saved under the download directory using the global path template from Settings."
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Display name</label>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Apple ID (iCloud)</label>
              <input
                value={appleIdEdit}
                onChange={(e) => setAppleIdEdit(e.target.value)}
                placeholder="apple@icloud.com"
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Download directory</label>
              <input
                value={downloadDir}
                onChange={(e) => setDownloadDir(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono"
              />
              <FieldHelp>
                Absolute path on the server. Must match an Immich external library import path if
                you use Immich. For iCloud + Google, use a path template with {"{source}"} in
                Settings.
              </FieldHelp>
            </div>
          </div>
        </Section>

        <Section
          title="Immich external library"
          description="Link this Apple ID to an Immich external library. Server URL and API key are configured in Settings."
        >
          <label className="flex items-center gap-2 text-sm text-slate-300 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={immichScanAfterSync}
              onChange={(e) => setImmichScanAfterSync(e.target.checked)}
              className="rounded"
            />
            Connect this user as an Immich external library
          </label>
          {immichScanAfterSync && (
            <div className="space-y-4">
              {immichLibraries.data?.libraries && immichLibraries.data.libraries.length > 0 ? (
                <div>
                  <label className="block text-sm text-slate-400 mb-1">External library</label>
                  <select
                    value={immichLibraryId}
                    onChange={(e) => setImmichLibraryId(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">Select a library…</option>
                    {immichLibraries.data.libraries.map((lib) => (
                      <option key={lib.id} value={lib.id}>
                        {lib.name}
                        {lib.importPaths?.length
                          ? ` — ${lib.importPaths.join(", ")}`
                          : ""}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <label className="block text-sm text-slate-400 mb-1">External library ID</label>
                  <input
                    value={immichLibraryId}
                    onChange={(e) => setImmichLibraryId(e.target.value)}
                    placeholder="UUID from Immich external library"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono"
                  />
                  {immichLibraries.isError && (
                    <p className="text-xs text-amber-400 mt-1">
                      Could not load libraries — configure Immich in Settings or paste the UUID
                      manually.
                    </p>
                  )}
                </div>
              )}
              <p className="text-xs text-slate-500">
                Download directory must be inside that library&apos;s import path in Immich. After
                each successful sync, a library scan is triggered.
              </p>
              <button
                type="button"
                onClick={() => testImmich.mutate()}
                disabled={testImmich.isPending || !immichLibraryId.trim()}
                className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
              >
                {testImmich.isPending ? "Calling Immich…" : "Test library scan"}
              </button>
            </div>
          )}
        </Section>

        <Section
          title="Sync all providers"
          description="Runs iCloud and Google in parallel. The scheduler uses this same behavior on each user's interval."
        >
          <FieldHelp className="mb-3">
            Blocked while a full <span className="font-mono">all</span> sync is already running.
            Per-provider sync buttons can still run side by side (e.g. iCloud + Google at once).
          </FieldHelp>
          <SyncNowButton
            userId={userId}
            disabled={!user.enabled || syncBusy.all}
            label="Sync all"
          />
        </Section>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => saveSettings.mutate({})}
            disabled={saveSettings.isPending || !downloadDir.trim()}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-5 py-2 rounded-lg text-sm font-medium"
          >
            {saveSettings.isPending ? "Saving…" : "Save settings"}
          </button>
          <button
            type="button"
            onClick={() => saveSettings.mutate({ reschedule_sync: true })}
            disabled={saveSettings.isPending || !scheduledEnabled}
            className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
            title="Set next sync to now + interval"
          >
            Reset next sync time
          </button>
        </div>
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
          </tr>
        </thead>
        <tbody>
          {syncRuns?.map((r) => (
            <tr key={r.id} className="border-b border-slate-800/50">
              <td className="py-2">#{r.id}</td>
              <td className="py-2 capitalize">{r.status}</td>
              <td className="py-2">{r.photos_downloaded}</td>
              <td className="py-2">{r.photos_failed}</td>
              <td className="py-2 text-slate-500">{new Date(r.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {(!syncRuns || syncRuns.length === 0) && (
        <p className="text-slate-500 text-sm mb-8">No sync runs yet.</p>
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
