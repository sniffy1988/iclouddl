import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../components/ToastProvider";
import AuthorizeButton from "../components/AuthorizeButton";
import { format2faDaysLeft } from "../utils/format2fa";
import StatusPill from "../components/StatusPill";
import ConnectGoogleButton from "../components/ConnectGoogleButton";
import ProviderConnectionBanner from "../components/ProviderConnectionBanner";
import FieldHelp, { HelpBox } from "../components/FieldHelp";
import FetchCountButton from "../components/FetchCountButton";
import SyncNowButton from "../components/SyncNowButton";
import {
  SYNC_INTERVAL_PRESETS,
  formatSyncInterval,
  hoursToSeconds,
  presetForSeconds,
  secondsToHours,
  syncIntervalPresetLabel,
} from "../utils/syncSchedule";
import { canCountIcloud, canSyncIcloud, hasSavedAppleId } from "../utils/icloudActions";
import { googleSectionDescription, icloudSectionDescription } from "../utils/providerStatus";

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
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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
      toast.success(t("google.connected"));
      qc.invalidateQueries({ queryKey: ["user", userId] });
      searchParams.delete("google");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, toast, qc, userId, t]);

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

  const deleteUser = useMutation({
    mutationFn: () => api.deleteUser(userId),
    onSuccess: () => {
      toast.success(t("userDetail.userDeleted"));
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      navigate("/users", { replace: true });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const saveSettings = useMutation({
    mutationFn: (opts?: { reschedule_sync?: boolean }) => {
      const seconds =
        intervalPreset === "custom"
          ? hoursToSeconds(parseFloat(customHours) || 6)
          : Number(intervalPreset);
      return api.updateUser(userId, {
        display_name:
          displayName.trim() ||
          user!.account_label ||
          user!.apple_id ||
          t("userDetail.defaultUserName"),
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
      toast.success(t("userDetail.settingsSaved"));
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (!user) return <div>{t("common.loading")}</div>;

  const isActive =
    user.activity_status === "queued" ||
    user.activity_status === "syncing" ||
    user.activity_status === "counting" ||
    user.activity_status === "counting_icloud" ||
    user.activity_status === "counting_google";

  const isCountingIcloud = user.activity_status === "counting_icloud";
  const isCountingGoogle = user.activity_status === "counting_google";
  const syncBusy = user.active_syncs_by_scope ?? {};
  const icloudCountOk = canCountIcloud(user, syncBusy);
  const icloudSyncOk = canSyncIcloud(user, syncBusy);
  const title =
    user.account_label ||
    user.display_name ||
    user.apple_id ||
    user.google_account_email ||
    t("common.userNumber", { id: user.id });

  const syncIntervalSeconds =
    intervalPreset === "custom"
      ? hoursToSeconds(parseFloat(customHours) || 6)
      : Number(intervalPreset);

  const activityMessage =
    user.activity_status === "counting_icloud"
      ? t("userDetail.indexingIcloud")
      : user.activity_status === "counting_google"
        ? t("userDetail.indexingGoogle")
        : user.activity_status === "counting"
          ? t("userDetail.indexingPhotos")
          : t("userDetail.syncInProgress");

  return (
    <div className="max-w-5xl">
      <div className="flex items-center gap-3 mb-2">
        <Link to="/users" className="text-slate-500 hover:text-slate-300 text-sm">
          {t("userDetail.backToUsers")}
        </Link>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="text-slate-500 text-sm mt-1">
            {t("userDetail.subtitle", { id: user.id })}
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
          <span className="text-sky-300 text-sm">{activityMessage}</span>
        </div>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">{t("userDetail.icloudPhotos")}</p>
          <p className="text-2xl font-semibold mt-1">
            {isCountingIcloud
              ? (user.icloud_photos_count ?? 0).toLocaleString()
              : (user.icloud_photos_count?.toLocaleString() ?? t("common.dash"))}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">{t("userDetail.googlePhotos")}</p>
          <p className="text-2xl font-semibold mt-1">
            {isCountingGoogle
              ? (user.google_photos_count ?? 0).toLocaleString()
              : (user.google_photos_count?.toLocaleString() ?? t("common.dash"))}
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">{t("userDetail.downloadedAll")}</p>
          <p className="text-2xl font-semibold mt-1">{counts?.downloaded_count ?? 0}</p>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <p className="text-slate-500 text-sm">{t("userDetail.remainingEst")}</p>
          <p className="text-2xl font-semibold mt-1">
            {isCountingIcloud || isCountingGoogle
              ? "…"
              : (counts?.remaining_to_download?.toLocaleString() ?? t("common.dash"))}
          </p>
        </div>
      </div>

      <div className="space-y-6 mb-8">
        <Section title={t("userDetail.icloudTitle")} description={icloudSectionDescription(user, t)}>
          <ProviderConnectionBanner
            provider="icloud"
            authStatus={user.icloud_auth_status}
            accountLabel={user.apple_id}
          />
          {!hasSavedAppleId(user) && (
            <p className="text-amber-400 text-sm mb-3">{t("userDetail.setAppleId")}</p>
          )}
          {!user.enabled && hasSavedAppleId(user) && (
            <p className="text-slate-500 text-sm mb-3">{t("userDetail.scheduledSyncOffManualOk")}</p>
          )}
          {user.icloud_auth_status === "awaiting_2fa" && (
            <HelpBox title={t("userDetail.awaiting2faTitle")}>
              <p className="text-slate-400 text-sm">{t("authorize.step2")}</p>
              <p className="text-slate-500 text-xs mt-2">{t("authorize.telegramHint")}</p>
            </HelpBox>
          )}
          {(user.icloud_auth_status === "not_authorized" ||
            user.icloud_auth_status === "reauth_required" ||
            user.icloud_auth_status === "expired") && (
            <HelpBox title={t("userDetail.beforeSignIn")}>
            <ul className="list-disc list-inside space-y-1">
              <li>{t("userDetail.icloudHelp1")}</li>
              <li>{t("userDetail.icloudHelp2")}</li>
              <li>{t("userDetail.icloudHelp3")}</li>
            </ul>
            </HelpBox>
          )}
          <div className="flex flex-wrap items-center gap-3 mb-3">
            {hasSavedAppleId(user) && (
              <>
                <AuthorizeButton
                  userId={userId}
                  appleId={user.apple_id!}
                  icloudAuthorized={user.icloud_authorized}
                  icloudNeedsAuth={user.icloud_needs_auth}
                  icloudPendingChallenge={user.icloud_pending_challenge}
                />
                {user.icloud_2fa_at && (
                  <span className="text-slate-400 text-sm">
                    {t("userDetail.trustedSession", {
                      label: format2faDaysLeft(user.days_until_2fa_expires),
                    })}
                  </span>
                )}
              </>
            )}
          </div>
          {user.icloud_authenticated_at && (
            <p className="text-xs text-slate-500 mb-3">
              {t("userDetail.lastSignIn", {
                time: new Date(user.icloud_authenticated_at).toLocaleString(),
              })}
            </p>
          )}
          <FieldHelp className="mb-3">{t("userDetail.countSyncHelp")}</FieldHelp>
          <div className="flex flex-wrap gap-2">
            <FetchCountButton
              userId={userId}
              source="icloud"
              disabled={!icloudCountOk}
              title={
                !icloudCountOk && !hasSavedAppleId(user)
                  ? t("userDetail.saveAppleIdFirst")
                  : undefined
              }
            />
            <SyncNowButton
              userId={userId}
              source="icloud"
              disabled={!icloudSyncOk}
              title={
                !icloudSyncOk && icloudCountOk
                  ? t("userDetail.signInIcloudFirst")
                  : undefined
              }
            />
          </div>
        </Section>

        <Section title={t("userDetail.googleTitle")} description={googleSectionDescription(user, t)}>
          <ProviderConnectionBanner
            provider="google"
            authStatus={user.google_auth_status}
            accountLabel={user.google_account_email}
          />
          {user.google_auth_status !== "authorized" && (
            <HelpBox title={t("userDetail.googleChecklist")}>
              <ol className="list-decimal list-inside space-y-1.5">
                <li>{t("userDetail.googleStep1")}</li>
                <li>{t("userDetail.googleStep2")}</li>
                <li>{t("userDetail.googleStep3")}</li>
              </ol>
            </HelpBox>
          )}
          <ConnectGoogleButton
            userId={userId}
            googleAuthorized={user.google_authorized}
            googleNeedsAuth={user.google_needs_auth}
          />
          <FieldHelp className="mt-3">{t("userDetail.googleConnectHelp")}</FieldHelp>
          <div className="flex flex-wrap gap-2 mt-4">
            <FetchCountButton
              userId={userId}
              source="google_photos"
              disabled={!user.google_authorized || syncBusy.google_photos}
            />
            <SyncNowButton
              userId={userId}
              source="google_photos"
              disabled={
                user.google_auth_status !== "authorized" || syncBusy.google_photos
              }
            />
          </div>
        </Section>

        <Section title={t("userDetail.scheduleTitle")} description={t("userDetail.scheduleDesc")}>
          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">{t("userDetail.interval")}</label>
              <select
                value={intervalPreset}
                onChange={(e) => setIntervalPreset(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              >
                {SYNC_INTERVAL_PRESETS.map((p) => (
                  <option key={p.seconds} value={String(p.seconds)}>
                    {syncIntervalPresetLabel(p.seconds)}
                  </option>
                ))}
                <option value="custom">{t("syncInterval.custom")}</option>
              </select>
            </div>
            {intervalPreset === "custom" && (
              <div>
                <label className="block text-sm text-slate-400 mb-1">{t("userDetail.hoursBetween")}</label>
                <input
                  type="number"
                  min={0.083}
                  step={0.5}
                  value={customHours}
                  onChange={(e) => setCustomHours(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                />
                <p className="text-xs text-slate-500 mt-1">{t("userDetail.minInterval")}</p>
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
            {t("userDetail.scheduledEnabled")}
          </label>

          <dl className="grid sm:grid-cols-2 gap-3 text-sm mb-4">
            <div className="bg-slate-800/50 rounded-lg px-3 py-2">
              <dt className="text-slate-500">{t("userDetail.currentInterval")}</dt>
              <dd className="text-slate-200 mt-0.5">{formatSyncInterval(syncIntervalSeconds)}</dd>
            </div>
            <div className="bg-slate-800/50 rounded-lg px-3 py-2">
              <dt className="text-slate-500">{t("userDetail.nextScheduled")}</dt>
              <dd className="text-slate-200 mt-0.5">
                {scheduledEnabled && user.next_sync_at
                  ? new Date(user.next_sync_at).toLocaleString()
                  : scheduledEnabled
                    ? t("common.soon")
                    : t("common.disabledParen")}
              </dd>
            </div>
            <div className="bg-slate-800/50 rounded-lg px-3 py-2">
              <dt className="text-slate-500">{t("userDetail.lastSync")}</dt>
              <dd className="text-slate-200 mt-0.5">
                {user.last_sync_at
                  ? new Date(user.last_sync_at).toLocaleString()
                  : t("common.dash")}
              </dd>
            </div>
          </dl>
        </Section>

        <Section title={t("userDetail.storageTitle")} description={t("userDetail.storageDesc")}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">{t("userDetail.displayName")}</label>
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">{t("userDetail.appleId")}</label>
              <input
                value={appleIdEdit}
                onChange={(e) => setAppleIdEdit(e.target.value)}
                placeholder={t("userDetail.appleIdPlaceholder")}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">{t("userDetail.downloadDir")}</label>
              <input
                value={downloadDir}
                onChange={(e) => setDownloadDir(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono"
              />
              <FieldHelp>{t("userDetail.downloadDirHelp")}</FieldHelp>
            </div>
          </div>
        </Section>

        <Section title={t("userDetail.immichTitle")} description={t("userDetail.immichDesc")}>
          <label className="flex items-center gap-2 text-sm text-slate-300 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={immichScanAfterSync}
              onChange={(e) => setImmichScanAfterSync(e.target.checked)}
              className="rounded"
            />
            {t("userDetail.immichConnect")}
          </label>
          {immichScanAfterSync && (
            <div className="space-y-4">
              {immichLibraries.data?.libraries && immichLibraries.data.libraries.length > 0 ? (
                <div>
                  <label className="block text-sm text-slate-400 mb-1">
                    {t("userDetail.externalLibrary")}
                  </label>
                  <select
                    value={immichLibraryId}
                    onChange={(e) => setImmichLibraryId(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                  >
                    <option value="">{t("userDetail.selectLibrary")}</option>
                    {immichLibraries.data.libraries.map((lib) => (
                      <option key={lib.id} value={lib.id}>
                        {lib.name}
                        {lib.importPaths?.length ? ` — ${lib.importPaths.join(", ")}` : ""}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <label className="block text-sm text-slate-400 mb-1">
                    {t("userDetail.externalLibraryId")}
                  </label>
                  <input
                    value={immichLibraryId}
                    onChange={(e) => setImmichLibraryId(e.target.value)}
                    placeholder={t("userDetail.libraryUuidPlaceholder")}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono"
                  />
                  {immichLibraries.isError && (
                    <p className="text-xs text-amber-400 mt-1">{t("userDetail.librariesLoadError")}</p>
                  )}
                </div>
              )}
              <p className="text-xs text-slate-500">{t("userDetail.immichPathHelp")}</p>
              <button
                type="button"
                onClick={() => testImmich.mutate()}
                disabled={testImmich.isPending || !immichLibraryId.trim()}
                className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
              >
                {testImmich.isPending
                  ? t("common.callingImmich")
                  : t("userDetail.testLibraryScan")}
              </button>
            </div>
          )}
        </Section>

        <Section title={t("userDetail.syncAllTitle")} description={t("userDetail.syncAllDesc")}>
          <FieldHelp className="mb-3">{t("userDetail.syncAllHelp")}</FieldHelp>
          <SyncNowButton
            userId={userId}
            disabled={syncBusy.all || (!icloudSyncOk && user.google_auth_status !== "authorized")}
            label={t("buttons.syncAll")}
          />
        </Section>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => saveSettings.mutate({})}
            disabled={saveSettings.isPending || !downloadDir.trim()}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-5 py-2 rounded-lg text-sm font-medium"
          >
            {saveSettings.isPending ? t("common.saving") : t("userDetail.saveSettings")}
          </button>
          <button
            type="button"
            onClick={() => saveSettings.mutate({ reschedule_sync: true })}
            disabled={saveSettings.isPending || !scheduledEnabled}
            className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
            title={t("userDetail.resetNextSyncTitle")}
          >
            {t("userDetail.resetNextSync")}
          </button>
        </div>
      </div>

      <h3 className="font-medium mb-3">{t("userDetail.recentSyncRuns")}</h3>
      <table className="w-full text-sm mb-8">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2">{t("userDetail.colRun")}</th>
            <th className="text-left py-2">{t("syncRuns.colStatus")}</th>
            <th className="text-left py-2">{t("syncRuns.colDownloaded")}</th>
            <th className="text-left py-2">{t("syncRuns.colFailed")}</th>
            <th className="text-left py-2">{t("syncRuns.colStarted")}</th>
          </tr>
        </thead>
        <tbody>
          {syncRuns?.map((r) => (
            <tr key={r.id} className="border-b border-slate-800/50">
              <td className="py-2">{t("common.runNumber", { id: r.id })}</td>
              <td className="py-2 capitalize">
                {t(`syncRunStatus.${r.status}`, { defaultValue: r.status })}
              </td>
              <td className="py-2">{r.photos_downloaded}</td>
              <td className="py-2">{r.photos_failed}</td>
              <td className="py-2 text-slate-500">{new Date(r.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {(!syncRuns || syncRuns.length === 0) && (
        <p className="text-slate-500 text-sm mb-8">{t("userDetail.noSyncRuns")}</p>
      )}

      <h3 className="font-medium mb-3">
        {t("userDetail.recentPhotos", { count: photos?.length ?? 0 })}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2">{t("userDetail.colFilename")}</th>
            <th className="text-left py-2">{t("syncRuns.colStatus")}</th>
            <th className="text-left py-2">{t("userDetail.colSize")}</th>
          </tr>
        </thead>
        <tbody>
          {photos?.slice(0, 20).map((p) => (
            <tr key={p.id} className="border-b border-slate-800/50">
              <td className="py-2">{p.filename}</td>
              <td className="py-2">{p.status}</td>
              <td className="py-2 text-slate-500">
                {p.file_size ? `${(p.file_size / 1024).toFixed(0)} KB` : t("common.dash")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <section className="mt-10 bg-slate-900 border border-red-900/40 rounded-xl p-5">
        <h3 className="font-medium text-red-300 mb-2">{t("userDetail.dangerZone")}</h3>
        <p className="text-slate-500 text-sm mb-4">{t("userDetail.deleteUserHint")}</p>
        <button
          type="button"
          onClick={() => setShowDeleteConfirm(true)}
          className="bg-red-900/60 hover:bg-red-800 border border-red-700/50 px-4 py-2 rounded-lg text-sm text-red-200"
        >
          {t("userDetail.deleteUser")}
        </button>
      </section>

      {showDeleteConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowDeleteConfirm(false)}
        >
          <div
            className="bg-slate-900 border border-red-800/60 rounded-xl p-6 w-full max-w-md shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-red-300 mb-2">{t("userDetail.deleteUserTitle")}</h3>
            <p className="text-slate-400 text-sm mb-6">
              {t("userDetail.deleteUserConfirm", { name: title })}
            </p>
            <div className="flex flex-wrap gap-3 justify-end">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-slate-200"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                onClick={() => deleteUser.mutate()}
                disabled={deleteUser.isPending}
                className="bg-red-700 hover:bg-red-600 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium"
              >
                {deleteUser.isPending ? t("userDetail.deletingUser") : t("userDetail.deleteUser")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
