import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../components/ToastProvider";

export default function Login() {
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
        Loading…
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
        Redirecting…
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
      toast.error(err instanceof Error ? err.message : "Login failed");
    }
  };

  const submitSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    if (password !== confirm) {
      toast.error("Passwords do not match");
      return;
    }
    try {
      await api.setupAdmin(password);
      toast.success("Admin account created");
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Setup failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form
        onSubmit={needsSetup ? submitSetup : submitLogin}
        className="bg-slate-900 border border-slate-800 rounded-xl p-8 w-full max-w-sm"
      >
        <h1 className="text-xl font-semibold mb-2">
          {needsSetup ? "Create admin account" : "Admin login"}
        </h1>
        <p className="text-slate-500 text-sm mb-6">
          {needsSetup
            ? "No admin exists yet. Choose a password — it is stored in the database."
            : "Sign in with your admin password."}
        </p>
        <label className="block text-sm text-slate-400 mb-1">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={needsSetup ? "At least 8 characters" : "Admin password"}
          autoComplete={needsSetup ? "new-password" : "current-password"}
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 mb-4"
        />
        {needsSetup && (
          <>
            <label className="block text-sm text-slate-400 mb-1">Confirm password</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Repeat password"
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
          {needsSetup ? "Create admin" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
