import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { useToast } from "../components/ToastProvider";

export default function Login() {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const navigate = useNavigate();
  const toast = useToast();

  const { data: status, isLoading } = useQuery({
    queryKey: ["auth-status"],
    queryFn: api.authStatus,
    retry: false,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-400">
        {t("common.loadingEllipsis")}
      </div>
    );
  }

  useEffect(() => {
    if (status?.authenticated) {
      navigate("/", { replace: true });
    }
  }, [status?.authenticated, navigate]);

  if (status?.authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-400">
        {t("common.redirecting")}
      </div>
    );
  }

  const needsSetup = status?.needs_setup ?? false;

  const submitLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.login(password);
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("login.loginFailed"));
    }
  };

  const submitSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error(t("login.passwordMin8"));
      return;
    }
    if (password !== confirm) {
      toast.error(t("login.passwordMismatch"));
      return;
    }
    try {
      await api.setupAdmin(password);
      toast.success(t("login.adminCreated"));
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("login.setupFailed"));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative">
      <div className="absolute top-4 right-4 w-40">
        <LanguageSwitcher compact />
      </div>
      <form
        onSubmit={needsSetup ? submitSetup : submitLogin}
        className="bg-slate-900 border border-slate-800 rounded-xl p-8 w-full max-w-sm"
      >
        <h1 className="text-xl font-semibold mb-2">
          {needsSetup ? t("login.createTitle") : t("login.loginTitle")}
        </h1>
        <p className="text-slate-500 text-sm mb-6">
          {needsSetup ? t("login.createHint") : t("login.loginHint")}
        </p>
        <label className="block text-sm text-slate-400 mb-1">{t("login.password")}</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={needsSetup ? t("login.placeholderMin8") : t("login.placeholderAdmin")}
          autoComplete={needsSetup ? "new-password" : "current-password"}
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 mb-4"
        />
        {needsSetup && (
          <>
            <label className="block text-sm text-slate-400 mb-1">{t("login.confirmPassword")}</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder={t("login.placeholderRepeat")}
              autoComplete="new-password"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 mb-4"
            />
          </>
        )}
        <button
          type="submit"
          disabled={!password || (needsSetup && !confirm)}
          className="w-full bg-sky-600 hover:bg-sky-500 disabled:opacity-50 rounded-lg py-2 font-medium"
        >
          {needsSetup ? t("login.createAdmin") : t("login.signIn")}
        </button>
      </form>
    </div>
  );
}
