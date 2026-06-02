import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/users", label: "Users" },
  { to: "/sync-runs", label: "Sync Runs" },
  { to: "/settings", label: "Settings" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation();

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 bg-slate-900 border-r border-slate-800 p-4 flex flex-col">
        <h1 className="text-lg font-semibold text-sky-400 mb-6">iCloud DL</h1>
        <nav className="flex flex-col gap-1 flex-1">
          {nav.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`px-3 py-2 rounded-lg text-sm ${
                loc.pathname === item.to
                  ? "bg-sky-600/30 text-sky-300"
                  : "text-slate-400 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <button
          onClick={() => api.logout().then(() => (window.location.href = "/login"))}
          className="text-sm text-slate-500 hover:text-slate-300 mt-4"
        >
          Logout
        </button>
      </aside>
      <main className="flex-1 p-8 overflow-auto">{children}</main>
    </div>
  );
}
