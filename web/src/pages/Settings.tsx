import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, SettingsData } from "../api/client";

const PATH_TEMPLATE_HELP =
  "Use / between folders. Tokens: YYYY, YY, MM, DD, HH, mm, ss, and {filename}. Example: YYYY/MM/DD/{filename}";

export default function Settings() {
  const qc = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: api.settings,
  });

  const [form, setForm] = useState<Partial<SettingsData>>({});
  const [tokenInput, setTokenInput] = useState("");
  const [saved, setSaved] = useState(false);

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
      });
      setTokenInput("");
    }
  }, [settings]);

  const save = useMutation({
    mutationFn: () =>
      api.updateSettings({
        ...form,
        telegram_bot_token: tokenInput || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      setTokenInput("");
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    },
  });

  const testTg = useMutation({ mutationFn: api.testTelegram });

  if (isLoading || !settings) return <div>Loading...</div>;

  const syncHours = (form.default_sync_interval_seconds ?? settings.default_sync_interval_seconds) / 3600;

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-semibold mb-2">Settings</h2>
      <p className="text-slate-500 text-sm mb-8">
        Saved to the database. Restart the worker after changing Telegram settings so the bot picks
        up a new token.
      </p>

      <form
        className="space-y-8"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h3 className="text-lg font-medium text-sky-300">Telegram</h3>

          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.telegram_enabled ?? false}
              onChange={(e) =>
                setForm((f) => ({ ...f, telegram_enabled: e.target.checked }))
              }
              className="rounded"
            />
            <span>Enable Telegram notifications and 2FA relay</span>
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
                  : "123456789:ABCdefGHI…"
              }
              autoComplete="off"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            {settings.telegram_bot_token_set && !tokenInput && (
              <p className="text-xs text-slate-500 mt-1">Current: {settings.telegram_bot_token_masked}</p>
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
            <p className="text-xs text-slate-500 mt-1">
              Chat or channel ID where sync alerts are sent.
            </p>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Allowed user IDs (optional)</label>
            <input
              value={form.telegram_allowed_user_ids ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, telegram_allowed_user_ids: e.target.value }))
              }
              placeholder="12345,67890"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <p className="text-xs text-slate-500 mt-1">
              Comma-separated Telegram user IDs allowed to send /code for 2FA.
            </p>
          </div>

          <button
            type="button"
            onClick={() => testTg.mutate()}
            disabled={testTg.isPending}
            className="bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded-lg text-sm"
          >
            {testTg.isPending ? "Sending…" : "Test Telegram notification"}
          </button>
          {testTg.data && (
            <p className={`text-sm ${testTg.data.ok ? "text-green-400" : "text-red-400"}`}>
              {testTg.data.ok ? "Test message sent" : "Failed — check token and chat ID, then Save"}
            </p>
          )}
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
              placeholder="YYYY/MM/DD/{filename}"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 font-mono text-sm"
            />
            <p className="text-xs text-slate-500 mt-2">{PATH_TEMPLATE_HELP}</p>
          </div>

          <div>
            <p className="text-sm text-slate-400">Base download directory (from environment)</p>
            <p className="font-mono text-sm mt-1 break-all">{settings.base_download_dir}</p>
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
          {saved && <span className="text-green-400 text-sm">Settings saved</span>}
          {save.isError && (
            <span className="text-red-400 text-sm">{(save.error as Error).message}</span>
          )}
        </div>
      </form>
    </div>
  );
}
