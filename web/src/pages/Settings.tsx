import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, SettingsData } from "../api/client";
import FieldHelp, { HelpBox } from "../components/FieldHelp";
import { useToast } from "../components/ToastProvider";
import { setDebugLoggingEnabled } from "../utils/debugLog";

const linkClass = "text-sky-400 hover:underline";
const monoClass = "font-mono text-slate-300";
const strongClass = "text-slate-300 font-semibold";

export default function Settings() {
  const { t } = useTranslation();
  const toast = useToast();
  const qc = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });

  const [form, setForm] = useState<Partial<SettingsData>>({});
  const [tokenInput, setTokenInput] = useState("");
  const [immichApiKeyInput, setImmichApiKeyInput] = useState("");
  const [adminPasswordInput, setAdminPasswordInput] = useState("");
  const [googleSecretInput, setGoogleSecretInput] = useState("");

  useEffect(() => {
    if (settings) {
      setForm({
        telegram_enabled: settings.telegram_enabled,
        download_path_template: settings.download_path_template,
        default_sync_interval_seconds: settings.default_sync_interval_seconds,
        max_concurrent_downloads: settings.max_concurrent_downloads,
        scheduler_poll_seconds: settings.scheduler_poll_seconds,
        immich_enabled: settings.immich_enabled,
        immich_base_url: settings.immich_base_url,
        immich_scan_debounce_seconds: settings.immich_scan_debounce_seconds,
        google_oauth_client_id: settings.google_oauth_client_id,
        debug_logging_enabled: settings.debug_logging_enabled,
      });
      setTokenInput("");
      setImmichApiKeyInput("");
      setAdminPasswordInput("");
      setGoogleSecretInput("");
    }
  }, [settings]);

  const save = useMutation({
    mutationFn: () =>
      api.updateSettings({
        ...form,
        telegram_bot_token: tokenInput || undefined,
        immich_api_key: immichApiKeyInput || undefined,
        admin_password: adminPasswordInput || undefined,
        google_oauth_client_secret: googleSecretInput || undefined,
      }),
    onSuccess: (updated) => {
      setDebugLoggingEnabled(Boolean(updated.debug_logging_enabled));
      qc.invalidateQueries({ queryKey: ["settings"] });
      setTokenInput("");
      setImmichApiKeyInput("");
      setAdminPasswordInput("");
      setGoogleSecretInput("");
      toast.success(t("settings.saved"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const testTg = useMutation({
    mutationFn: api.testTelegram,
    onSuccess: (data) => {
      if (data.ok) toast.success(t("settings.testMessageSent"));
      else toast.error(t("settings.testMessageFailed"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const testImmich = useMutation({
    mutationFn: () => api.testImmich(),
    onSuccess: (data) => {
      if (data.ok) toast.success(data.message);
      else toast.error(data.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  if (isLoading || !settings) return <div>{t("common.loading")}</div>;

  const syncHours = (form.default_sync_interval_seconds ?? settings.default_sync_interval_seconds) / 3600;
  const redirectUri = settings.google_oauth_redirect_uri;

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2">{t("settings.title")}</h2>
      <p className="text-slate-500 text-sm mb-8">{t("settings.intro")}</p>

      <form
        className="space-y-8"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-amber-300">{t("settings.adminLogin")}</h3>
          <FieldHelp>{t("settings.adminLoginHelp")}</FieldHelp>
          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.newAdminPassword")}</label>
            <input
              type="password"
              value={adminPasswordInput}
              onChange={(e) => setAdminPasswordInput(e.target.value)}
              placeholder={
                settings.admin_password_set
                  ? t("settings.keepPassword")
                  : t("login.placeholderMin8")
              }
              autoComplete="new-password"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            {settings.admin_password_set && (
              <FieldHelp>{t("settings.passwordAlreadySet")}</FieldHelp>
            )}
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-sky-300">{t("settings.telegram")}</h3>

          <HelpBox title={t("settings.helpWhereToGet")}>
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                <Trans
                  i18nKey="settings.telegramHelp1"
                  components={{
                    1: (
                      <a
                        href="https://t.me/BotFather"
                        target="_blank"
                        rel="noopener noreferrer"
                        className={linkClass}
                      />
                    ),
                  }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.telegramHelp2"
                  components={{
                    1: <span className={monoClass} />,
                    2: <strong className={strongClass} />,
                    3: <span className="font-mono" />,
                  }}
                />
              </li>
              <li>{t("settings.telegramHelp3")}</li>
            </ol>
          </HelpBox>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.telegram_enabled ?? false}
              onChange={(e) =>
                setForm((f) => ({ ...f, telegram_enabled: e.target.checked }))
              }
              className="rounded"
            />
            <span>{t("settings.enableTelegram")}</span>
          </label>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.botToken")}</label>
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder={
                settings.telegram_bot_token_set
                  ? settings.telegram_bot_token_masked || t("settings.tokenMaskedKeep")
                  : t("settings.tokenFromBotFather")
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            {settings.telegram_bot_token_set && !tokenInput && (
              <FieldHelp>
                {t("settings.tokenEndsWith", { masked: settings.telegram_bot_token_masked })}
              </FieldHelp>
            )}
          </div>

          <button
            type="button"
            onClick={() => testTg.mutate()}
            disabled={testTg.isPending}
            className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
          >
            {testTg.isPending ? t("common.connecting") : t("settings.testBotToken")}
          </button>
          <FieldHelp>{t("settings.testBotHelp")}</FieldHelp>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-violet-300">{t("settings.downloadPaths")}</h3>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.photoPathTemplate")}</label>
            <input
              value={form.download_path_template ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, download_path_template: e.target.value }))
              }
              placeholder={t("settings.pathTemplatePlaceholder")}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>{t("settings.pathTemplateHelp")}</FieldHelp>
          </div>

          <div>
            <p className="text-sm text-slate-400">{t("settings.baseDownloadDir")}</p>
            <p className="font-mono text-sm mt-1 break-all">{settings.base_download_dir}</p>
            <FieldHelp>{t("settings.baseDirHelp")}</FieldHelp>
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-violet-300">{t("settings.immich")}</h3>
          <FieldHelp>{t("settings.immichHelp")}</FieldHelp>

          <HelpBox title={t("settings.immichHelpTitle")}>
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                <Trans
                  i18nKey="settings.immichHelp1"
                  components={{ 1: <strong className={strongClass} /> }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.immichHelp2"
                  components={{
                    1: <strong className={strongClass} />,
                    2: <span className="font-mono" />,
                    3: <span className="font-mono" />,
                  }}
                />
              </li>
              <li>{t("settings.immichHelp3")}</li>
              <li>
                <Trans
                  i18nKey="settings.immichHelp4"
                  components={{ 1: <strong className={strongClass} /> }}
                />
              </li>
            </ol>
          </HelpBox>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.immich_enabled ?? false}
              onChange={(e) =>
                setForm((f) => ({ ...f, immich_enabled: e.target.checked }))
              }
              className="rounded"
            />
            <span>{t("settings.enableImmich")}</span>
          </label>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.immichServerUrl")}</label>
            <input
              value={form.immich_base_url ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, immich_base_url: e.target.value }))
              }
              placeholder={t("settings.immichUrlPlaceholder")}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>{t("settings.immichUrlHelp")}</FieldHelp>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.apiKey")}</label>
            <input
              type="password"
              value={immichApiKeyInput}
              onChange={(e) => setImmichApiKeyInput(e.target.value)}
              placeholder={
                settings.immich_api_key_set
                  ? t("settings.apiKeyKeep", { masked: settings.immich_api_key_masked })
                  : t("settings.apiKeyPlaceholder")
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.scanDebounce")}</label>
            <input
              type="number"
              min={0}
              max={3600}
              value={form.immich_scan_debounce_seconds ?? settings.immich_scan_debounce_seconds}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  immich_scan_debounce_seconds: Number(e.target.value),
                }))
              }
              className="w-32 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <FieldHelp>{t("settings.scanDebounceHelp")}</FieldHelp>
          </div>

          <button
            type="button"
            onClick={() => testImmich.mutate()}
            disabled={testImmich.isPending}
            className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
          >
            {testImmich.isPending ? t("common.connecting") : t("settings.testImmich")}
          </button>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-blue-300">{t("settings.googleOAuth")}</h3>
          <FieldHelp>{t("settings.googleOAuthHelp")}</FieldHelp>

          {!settings.token_encryption_key_set && (
            <div className="rounded-lg border border-amber-700/60 bg-amber-900/20 px-3 py-2 text-xs text-amber-200">
              <strong>TOKEN_ENCRYPTION_KEY</strong> {t("settings.tokenKeyMissing")}
              <span className="font-mono block mt-1 text-amber-100/90">{t("settings.tokenKeyCmd")}</span>
            </div>
          )}

          <HelpBox title={t("settings.serverEnvTitle")}>
            <ul className="list-disc list-inside space-y-1.5">
              <li>
                <Trans
                  i18nKey="settings.serverEnvWebUrl"
                  values={{ url: settings.web_public_base_url }}
                  components={{
                    1: <span className={monoClass} />,
                    2: <span className="font-mono" />,
                  }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.serverEnvTokenKey"
                  components={{ 1: <span className={monoClass} /> }}
                />
              </li>
            </ul>
            {settings.token_encryption_key_set && (
              <p className="text-emerald-400/90 mt-2">{t("settings.tokenKeyConfigured")}</p>
            )}
          </HelpBox>

          <HelpBox title={t("settings.googleConsoleTitle")}>
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                <Trans
                  i18nKey="settings.googleConsole1"
                  components={{
                    1: (
                      <a
                        href="https://console.cloud.google.com/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className={linkClass}
                      />
                    ),
                  }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.googleConsole2"
                  components={{
                    1: <strong className={strongClass} />,
                    2: <strong className={strongClass} />,
                  }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.googleConsole3"
                  components={{ 1: <strong className={strongClass} /> }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.googleConsole4"
                  components={{
                    1: <strong className={strongClass} />,
                    2: <strong className={strongClass} />,
                  }}
                />
              </li>
              <li>
                <Trans
                  i18nKey="settings.googleConsole5"
                  components={{ 1: <strong className={strongClass} /> }}
                />
                <span className="block font-mono text-sky-300/90 mt-1 break-all">{redirectUri}</span>
              </li>
              <li>
                <Trans
                  i18nKey="settings.googleConsole6"
                  components={{
                    1: <strong className={strongClass} />,
                    2: <strong className={strongClass} />,
                  }}
                />
              </li>
            </ol>
          </HelpBox>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.oauthClientId")}</label>
            <input
              value={form.google_oauth_client_id ?? settings.google_oauth_client_id ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, google_oauth_client_id: e.target.value }))
              }
              placeholder={t("settings.oauthClientIdPlaceholder")}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>{t("settings.oauthClientIdHelp")}</FieldHelp>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.oauthClientSecret")}</label>
            <input
              type="password"
              value={googleSecretInput}
              onChange={(e) => setGoogleSecretInput(e.target.value)}
              placeholder={
                settings.google_oauth_client_secret_set
                  ? t("settings.oauthSecretKeep", {
                      masked: settings.google_oauth_client_secret_masked,
                    })
                  : t("settings.oauthSecretPlaceholder")
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>{t("settings.oauthSecretHelp")}</FieldHelp>
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-violet-300">{t("settings.loggingSection")}</h3>
          <FieldHelp>{t("settings.loggingHelp")}</FieldHelp>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.debug_logging_enabled ?? settings.debug_logging_enabled ?? false}
              onChange={(e) =>
                setForm((f) => ({ ...f, debug_logging_enabled: e.target.checked }))
              }
              className="rounded"
            />
            <span>{t("settings.debugLoggingEnabled")}</span>
          </label>
          <p className="text-slate-500 text-sm">
            <Link to="/logs" className="text-sky-400 hover:underline">
              {t("settings.viewLogs")}
            </Link>
          </p>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-slate-300">{t("settings.syncSection")}</h3>

          <div>
            <label className="block text-sm text-slate-400 mb-1">{t("settings.defaultSyncInterval")}</label>
            <input
              type="number"
              min={1}
              step={1}
              value={syncHours}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  default_sync_interval_seconds: Math.max(3600, Number(e.target.value) * 3600),
                }))
              }
              className="w-32 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            <FieldHelp>{t("settings.defaultSyncHelp")}</FieldHelp>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">{t("settings.maxConcurrent")}</label>
              <input
                type="number"
                min={1}
                max={32}
                value={form.max_concurrent_downloads ?? settings.max_concurrent_downloads}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    max_concurrent_downloads: Number(e.target.value),
                  }))
                }
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
              />
              <FieldHelp>{t("settings.maxConcurrentHelp")}</FieldHelp>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">{t("settings.schedulerPoll")}</label>
              <input
                type="number"
                min={10}
                max={3600}
                value={form.scheduler_poll_seconds ?? settings.scheduler_poll_seconds}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    scheduler_poll_seconds: Number(e.target.value),
                  }))
                }
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
              />
              <FieldHelp>{t("settings.schedulerPollHelp")}</FieldHelp>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="submit"
            disabled={save.isPending}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-6 py-2.5 rounded-lg font-medium"
          >
            {save.isPending ? t("common.saving") : t("settings.saveSettings")}
          </button>
        </div>
      </form>
    </div>
  );
}
