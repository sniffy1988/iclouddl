import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client";
import LanguageSwitcher from "./LanguageSwitcher";
import RealtimeIndicator from "./RealtimeIndicator";

const navItems = [
  { to: "/", key: "dashboard" as const },
  { to: "/users", key: "users" as const },
  { to: "/sync-runs", key: "syncRuns" as const },
  { to: "/logs", key: "logs" as const },
  { to: "/settings", key: "settings" as const },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation();
  const { t } = useTranslation();

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 bg-slate-900 border-r border-slate-800 p-4 flex flex-col">
        <h1 className="text-lg font-semibold text-sky-400 mb-6">{t("app.brand")}</h1>
        <nav className="flex flex-col gap-1 flex-1">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`px-3 py-2 rounded-lg text-sm ${
                loc.pathname === item.to
                  ? "bg-sky-600/30 text-sky-300"
                  : "text-slate-400 hover:bg-slate-800"
              }`}
            >
              {t(`nav.${item.key}`)}
            </Link>
          ))}
        </nav>
        <LanguageSwitcher />
        <RealtimeIndicator />
        <button
          onClick={() => api.logout().then(() => (window.location.href = "/login"))}
          className="text-sm text-slate-500 hover:text-slate-300 mt-4"
        >
          {t("nav.logout")}
        </button>
      </aside>
      <main className="flex-1 p-8 overflow-auto">{children}</main>
    </div>
  );
}
