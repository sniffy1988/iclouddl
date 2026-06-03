import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes } from "react-router-dom";
import DebugLoggingSync from "./components/DebugLoggingSync";
import Layout from "./components/Layout";
import RealtimeProvider from "./components/RealtimeProvider";
import { ToastProvider } from "./components/ToastProvider";
import Dashboard from "./pages/Dashboard";
import Logs from "./pages/Logs";
import Login from "./pages/Login";
import Settings from "./pages/Settings";
import SyncRuns from "./pages/SyncRuns";
import UserDetail from "./pages/UserDetail";
import Users from "./pages/Users";
import { api } from "./api/client";

function Protected({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const { isLoading, isError } = useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
  });
  if (isLoading) return <div className="p-8">{t("common.loading")}</div>;
  if (isError) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <Protected>
              <RealtimeProvider>
                <DebugLoggingSync />
                <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/users" element={<Users />} />
                  <Route path="/users/:id" element={<UserDetail />} />
                  <Route path="/sync-runs" element={<SyncRuns />} />
                  <Route path="/logs" element={<Logs />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
                </Layout>
              </RealtimeProvider>
            </Protected>
          }
        />
      </Routes>
    </ToastProvider>
  );
}
