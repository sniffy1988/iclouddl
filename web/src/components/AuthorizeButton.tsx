import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  appleId: string;
  icloudAuthorized?: boolean;
  icloudNeedsAuth?: boolean;
  size?: "sm" | "md";
};

type Step = "password" | "2fa";

export default function AuthorizeButton({
  userId,
  appleId,
  icloudAuthorized = false,
  icloudNeedsAuth = true,
  size = "md",
}: Props) {
  if (icloudAuthorized && !icloudNeedsAuth) {
    return null;
  }
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("password");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [deliveryHint, setDeliveryHint] = useState<string | null>(null);

  const { data: challenge } = useQuery({
    queryKey: ["challenge", userId],
    queryFn: () => api.getPendingChallenge(userId),
    enabled: open && step === "2fa",
    refetchInterval: open && step === "2fa" ? 3000 : false,
  });

  const openModal = () => {
    setOpen(true);
    setStep("password");
    setPassword("");
    setCode("");
    setDeliveryHint(null);
  };

  const closeModal = () => {
    setOpen(false);
    setStep("password");
    setPassword("");
    setCode("");
    setDeliveryHint(null);
  };

  const login = useMutation({
    mutationFn: () => api.startICloudAuth(userId, password),
    onSuccess: (result) => {
      if (result.status === "authenticated") {
        closeModal();
        toast.success("iCloud authorized");
        qc.invalidateQueries({ queryKey: ["users"] });
        qc.invalidateQueries({ queryKey: ["user", userId] });
      } else {
        setStep("2fa");
        setCode("");
        if (result.message) {
          setDeliveryHint(result.message);
        }
        qc.invalidateQueries({ queryKey: ["challenge", userId] });
        qc.invalidateQueries({ queryKey: ["users"] });
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const submit2fa = useMutation({
    mutationFn: () => api.submit2FA(userId, code.trim(), challenge?.id, password),
    onSuccess: () => {
      closeModal();
      toast.success("iCloud authorized");
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["challenge", userId] });
    },
    onError: (err: Error) => {
      const msg = err.message;
      if (
        msg.includes("No active iCloud session") ||
        msg.includes("run auth login") ||
        msg.includes("No pending auth challenge")
      ) {
        setStep("password");
        toast.warning("Session expired — enter your password and sign in again.");
      } else {
        toast.error(msg);
      }
    },
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";
  return (
    <>
      <button
        type="button"
        onClick={openModal}
        title="Sign in to iCloud with Apple ID password"
        className={`rounded-lg font-medium disabled:opacity-50 ${pad} ${
          icloudNeedsAuth
            ? "bg-amber-600 hover:bg-amber-500"
            : "bg-emerald-700 hover:bg-emerald-600"
        }`}
      >
        Authorize
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={closeModal}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold mb-1">Authorize iCloud</h3>
            <p className="text-slate-500 text-sm mb-4 break-all">{appleId}</p>

            {step === "password" && (
              <div className="space-y-3 mb-4">
                <p className="text-slate-400 text-sm">
                  Step 1 — enter your Apple ID password (not an app-specific password unless you use
                  one for iCloud). If 2FA is enabled, you will be asked for a code next.
                </p>
                <p className="text-slate-500 text-xs">
                  Requires “Access iCloud Data on the Web” on the device and Advanced Data
                  Protection turned off. See user page for details.
                </p>
                <label className="block text-sm text-slate-400">Apple ID password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && password && !login.isPending) login.mutate();
                  }}
                  autoComplete="current-password"
                  autoFocus
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2"
                  placeholder="Password"
                />
                <button
                  type="button"
                  onClick={() => login.mutate()}
                  disabled={!password || login.isPending}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 py-2 rounded-lg text-sm font-medium"
                >
                  {login.isPending ? "Signing in…" : "Sign in"}
                </button>
              </div>
            )}

            {step === "2fa" && (
              <div className="space-y-3 mb-4">
                <p className="text-amber-300 text-sm">
                  Step 2 — enter the 6-digit code. You only need one code (from the Mac/iPhone
                  popup or SMS — they are usually the same).
                </p>
                {deliveryHint && (
                  <p className="text-slate-400 text-xs">{deliveryHint}</p>
                )}
                <p className="text-slate-500 text-xs">
                  Do not click Sign in again — that sends another code. Or send{" "}
                  <span className="font-mono">/code 123456</span> to your Telegram bot if allowed in
                  Settings.
                </p>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && code.length >= 4 && !submit2fa.isPending)
                      submit2fa.mutate();
                  }}
                  placeholder="123456"
                  autoFocus
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 tracking-widest"
                  maxLength={8}
                />
                <button
                  type="button"
                  onClick={() => submit2fa.mutate()}
                  disabled={code.length < 4 || submit2fa.isPending}
                  className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-50 py-2 rounded-lg text-sm font-medium"
                >
                  {submit2fa.isPending ? "Verifying…" : "Verify code"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStep("password");
                    setCode("");
                  }}
                  className="text-slate-500 text-xs hover:text-slate-300"
                >
                  ← Back to password
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={closeModal}
              className="text-slate-500 text-sm hover:text-slate-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </>
  );
}
