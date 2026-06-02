import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, SettingsData } from "../api/client";
import FieldHelp, { HelpBox } from "../components/FieldHelp";
import { useToast } from "../components/ToastProvider";

const PATH_TEMPLATE_HELP =
  "Use / between folders. Tokens: YYYY, YY, MM, DD, HH, mm, ss, {source}, and {filename}. For iCloud + Google on one user, include {source} so files do not overwrite each other.";

export default function Settings() {
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
        telegram_admin_chat_id: settings.telegram_admin_chat_id,
        telegram_allowed_user_ids: settings.telegram_allowed_user_ids,
        download_path_template: settings.download_path_template,
        default_sync_interval_seconds: settings.default_sync_interval_seconds,
        max_concurrent_downloads: settings.max_concurrent_downloads,
        scheduler_poll_seconds: settings.scheduler_poll_seconds,
        immich_enabled: settings.immich_enabled,
        immich_base_url: settings.immich_base_url,
        immich_scan_debounce_seconds: settings.immich_scan_debounce_seconds,
        google_oauth_client_id: settings.google_oauth_client_id,
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      setTokenInput("");
      setImmichApiKeyInput("");
      setAdminPasswordInput("");
      setGoogleSecretInput("");
      toast.success("Settings saved");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const testTg = useMutation({
    mutationFn: api.testTelegram,
    onSuccess: (data) => {
      if (data.ok) toast.success("Test message sent");
      else toast.error("Failed — check token and chat ID, then Save");
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
  if (isLoading || !settings) return <div>Loading...</div>;

  const syncHours = (form.default_sync_interval_seconds ?? settings.default_sync_interval_seconds) / 3600;
  const redirectUri = settings.google_oauth_redirect_uri;

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2">Settings</h2>
      <p className="text-slate-500 text-sm mb-8">
        Values saved here are stored in the database. Some secrets must still be set in the server{" "}
        <span className="font-mono text-slate-400">.env</span> file (see Google Photos section).
        Restart the worker after changing the Telegram bot token.
      </p>

      <form
        className="space-y-8"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-amber-300">Admin login</h3>
          <FieldHelp>
            Password for this web UI only. On first visit, use the login screen to create the
            initial admin account (stored as a bcrypt hash in the database).
          </FieldHelp>
          <div>
            <label className="block text-sm text-slate-400 mb-1">New admin password</label>
            <input
              type="password"
              value={adminPasswordInput}
              onChange={(e) => setAdminPasswordInput(e.target.value)}
              placeholder={
                settings.admin_password_set
                  ? "Leave blank to keep current password"
                  : "At least 8 characters"
              }
              autoComplete="new-password"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
            />
            {settings.admin_password_set && (
              <FieldHelp>A password is already stored. Enter a new one only to change it.</FieldHelp>
            )}
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-sky-300">Telegram</h3>

          <HelpBox title="Where to get these values">
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                Open Telegram and message{" "}
                <a
                  href="https://t.me/BotFather"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-400 hover:underline"
                >
                  @BotFather
                </a>
                .
              </li>
              <li>
                Send <span className="font-mono text-slate-300">/newbot</span>, follow prompts, then
                copy the <strong className="text-slate-300">HTTP API token</strong> (looks like{" "}
                <span className="font-mono">123456789:AAH…</span>).
              </li>
              <li>
                For <strong className="text-slate-300">Admin chat ID</strong>: add your bot to a
                group/channel, send a message, then open{" "}
                <span className="font-mono text-slate-300">
                  https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates
                </span>{" "}
                and find <span className="font-mono">chat.id</span> (often negative for groups).
              </li>
              <li>
                Optional <strong className="text-slate-300">Allowed user IDs</strong>: your numeric
                Telegram user ID from bots like{" "}
                <a
                  href="https://t.me/userinfobot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-400 hover:underline"
                >
                  @userinfobot
                </a>{" "}
                — required for <span className="font-mono">/code</span> 2FA relay.
              </li>
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
            <span>Enable Telegram (daemon status + optional 2FA bot)</span>
          </label>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Bot token</label>
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder={
                settings.telegram_bot_token_set
                  ? settings.telegram_bot_token_masked || "•••••••• (leave blank to keep)"
                  : "From @BotFather after /newbot"
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            {settings.telegram_bot_token_set && !tokenInput && (
              <FieldHelp>Current token ends with: {settings.telegram_bot_token_masked}</FieldHelp>
            )}
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Admin chat ID</label>
            <input
              value={form.telegram_admin_chat_id ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, telegram_admin_chat_id: e.target.value }))
              }
              placeholder="-1001234567890"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>Group or channel ID where daemon sync/count alerts are posted.</FieldHelp>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Allowed user IDs (optional)</label>
            <input
              value={form.telegram_allowed_user_ids ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, telegram_allowed_user_ids: e.target.value }))
              }
              placeholder="123456789,987654321"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>
              Comma-separated Telegram user IDs allowed to send{" "}
              <span className="font-mono">/code 123456</span> for iCloud 2FA.
            </FieldHelp>
          </div>

          <button
            type="button"
            onClick={() => testTg.mutate()}
            disabled={testTg.isPending}
            className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
          >
            {testTg.isPending ? "Sending…" : "Test daemon status message"}
          </button>
          <FieldHelp>
            Sends a test message to the admin chat. Save token and chat ID first. Admin chat
            receives daemon events only (not per-user Immich or auth errors).
          </FieldHelp>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-violet-300">Download paths</h3>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Photo path template</label>
            <input
              value={form.download_path_template ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, download_path_template: e.target.value }))
              }
              placeholder="{source}/YYYY/MM/DD/{filename}"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>{PATH_TEMPLATE_HELP}</FieldHelp>
          </div>

          <div>
            <p className="text-sm text-slate-400">Base download directory (from environment)</p>
            <p className="font-mono text-sm mt-1 break-all">{settings.base_download_dir}</p>
            <FieldHelp>
              Set <span className="font-mono">BASE_DOWNLOAD_DIR</span> in .env. Each user also has
              their own folder under this path.
            </FieldHelp>
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-violet-300">Immich</h3>
          <FieldHelp>
            Connects to your Immich server for optional library scans after sync. Per-user external
            library ID is set on each user page.
          </FieldHelp>

          <HelpBox title="Where to get Immich API key">
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                Open your Immich web app → <strong className="text-slate-300">Account settings</strong>{" "}
                (avatar menu).
              </li>
              <li>
                <strong className="text-slate-300">API Keys</strong> → Create key with permissions{" "}
                <span className="font-mono">library.read</span> and{" "}
                <span className="font-mono">library.update</span> (or admin key for testing).
              </li>
              <li>
                Copy the key once shown — Immich does not display it again.
              </li>
              <li>
                External library UUID: Immich → <strong className="text-slate-300">Administration</strong>{" "}
                → External libraries → open library → copy ID from URL or settings.
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
            <span>Enable Immich library scans</span>
          </label>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Immich server URL</label>
            <input
              value={form.immich_base_url ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, immich_base_url: e.target.value }))
              }
              placeholder="https://photos.example.com"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>Public base URL of Immich (no trailing slash), same host you use in the browser.</FieldHelp>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">API key</label>
            <input
              type="password"
              value={immichApiKeyInput}
              onChange={(e) => setImmichApiKeyInput(e.target.value)}
              placeholder={
                settings.immich_api_key_set
                  ? `${settings.immich_api_key_masked} (leave blank to keep)`
                  : "Paste Immich API key"
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Scan debounce (seconds)
            </label>
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
            <FieldHelp>Minimum seconds between scan requests for the same library.</FieldHelp>
          </div>

          <button
            type="button"
            onClick={() => testImmich.mutate()}
            disabled={testImmich.isPending}
            className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
          >
            {testImmich.isPending ? "Connecting…" : "Test Immich connection"}
          </button>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-blue-300">Google Photos OAuth</h3>
          <FieldHelp>
            Global OAuth app credentials. Each user connects their own Google account on their user
            page. Refresh tokens are encrypted in the database.
          </FieldHelp>

          {!settings.token_encryption_key_set && (
            <div className="rounded-lg border border-amber-700/60 bg-amber-900/20 px-3 py-2 text-xs text-amber-200">
              <strong>TOKEN_ENCRYPTION_KEY</strong> is not set in .env — Google connect will fail
              until you add it and restart the API/worker. Generate:{" "}
              <span className="font-mono block mt-1 text-amber-100/90">
                python -c &quot;from cryptography.fernet import Fernet;
                print(Fernet.generate_key().decode())&quot;
              </span>
            </div>
          )}

          <HelpBox title="Server .env (not stored in database)">
            <ul className="list-disc list-inside space-y-1.5">
              <li>
                <span className="font-mono text-slate-300">WEB_PUBLIC_BASE_URL</span> — exact URL
                you use to open this app (e.g.{" "}
                <span className="font-mono">{settings.web_public_base_url}</span>). Must match
                Google redirect host.
              </li>
              <li>
                <span className="font-mono text-slate-300">TOKEN_ENCRYPTION_KEY</span> — Fernet key
                from the command above. Back up with your database; losing it invalidates stored
                Google tokens.
              </li>
            </ul>
            {settings.token_encryption_key_set && (
              <p className="text-emerald-400/90 mt-2">TOKEN_ENCRYPTION_KEY is configured.</p>
            )}
          </HelpBox>

          <HelpBox title="Google Cloud Console — OAuth client">
            <ol className="list-decimal list-inside space-y-1.5">
              <li>
                <a
                  href="https://console.cloud.google.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sky-400 hover:underline"
                >
                  Google Cloud Console
                </a>{" "}
                → create or select a project.
              </li>
              <li>
                <strong className="text-slate-300">APIs & Services → Library</strong> → enable{" "}
                <strong className="text-slate-300">Photos Library API</strong>.
              </li>
              <li>
                <strong className="text-slate-300">APIs & Services → OAuth consent screen</strong>{" "}
                → configure (External + test users, or publish app).
              </li>
              <li>
                <strong className="text-slate-300">Credentials → Create credentials → OAuth client
                ID</strong> → type <strong className="text-slate-300">Web application</strong>.
              </li>
              <li>
                Under <strong className="text-slate-300">Authorized redirect URIs</strong>, add
                exactly:
                <span className="block font-mono text-sky-300/90 mt-1 break-all">{redirectUri}</span>
              </li>
              <li>
                Copy <strong className="text-slate-300">Client ID</strong> and{" "}
                <strong className="text-slate-300">Client secret</strong> below, then Save.
              </li>
            </ol>
          </HelpBox>

          <div>
            <label className="block text-sm text-slate-400 mb-1">OAuth client ID</label>
            <input
              value={form.google_oauth_client_id ?? settings.google_oauth_client_id ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, google_oauth_client_id: e.target.value }))
              }
              placeholder="123456789-abc.apps.googleusercontent.com"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>From Google Cloud → Credentials → your OAuth 2.0 Client ID.</FieldHelp>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">OAuth client secret</label>
            <input
              type="password"
              value={googleSecretInput}
              onChange={(e) => setGoogleSecretInput(e.target.value)}
              placeholder={
                settings.google_oauth_client_secret_set
                  ? `${settings.google_oauth_client_secret_masked} (leave blank to keep)`
                  : "GOCSPX-… from same credentials page"
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <FieldHelp>Shown once when the client is created. Store only here (database), not in git.</FieldHelp>
          </div>
        </section>

        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-slate-300">Sync</h3>

          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Default sync interval (hours)
            </label>
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
            <FieldHelp>Default for new users. Each user can override on their profile.</FieldHelp>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Max concurrent downloads</label>
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
              <FieldHelp>Split across providers when iCloud and Google sync overlap.</FieldHelp>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Scheduler poll (seconds)</label>
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
              <FieldHelp>How often the worker checks for users due for scheduled sync.</FieldHelp>
            </div>
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="submit"
            disabled={save.isPending}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-6 py-2.5 rounded-lg font-medium"
          >
            {save.isPending ? "Saving…" : "Save settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
