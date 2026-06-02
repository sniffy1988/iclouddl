import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
        toast.success(t("authorize.icloudAuthorized"));
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
      toast.success(t("authorize.icloudAuthorized"));
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
        toast.warning(t("authorize.sessionExpired"));
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
        title={t("authorize.authorizeTitle")}
        className={`rounded-lg font-medium disabled:opacity-50 ${pad} ${
          icloudNeedsAuth
            ? "bg-amber-600 hover:bg-amber-500"
            : "bg-emerald-700 hover:bg-emerald-600"
        }`}
      >
        {t("buttons.authorize")}
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
            <h3 className="text-lg font-semibold mb-1">{t("authorize.title")}</h3>
            <p className="text-slate-500 text-sm mb-4 break-all">{appleId}</p>

            {step === "password" && (
              <div className="space-y-3 mb-4">
                <p className="text-slate-400 text-sm">{t("authorize.step1")}</p>
                <p className="text-slate-500 text-xs">{t("authorize.requirements")}</p>
                <label className="block text-sm text-slate-400">{t("authorize.applePassword")}</label>
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
                  placeholder={t("authorize.passwordPlaceholder")}
                />
                <button
                  type="button"
                  onClick={() => login.mutate()}
                  disabled={!password || login.isPending}
                  className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 py-2 rounded-lg text-sm font-medium"
                >
                  {login.isPending ? t("common.signingIn") : t("authorize.signIn")}
                </button>
              </div>
            )}

            {step === "2fa" && (
              <div className="space-y-3 mb-4">
                <p className="text-amber-300 text-sm">{t("authorize.step2")}</p>
                {deliveryHint && (
                  <p className="text-slate-400 text-xs">{deliveryHint}</p>
                )}
                <p className="text-slate-500 text-xs">{t("authorize.telegramHint")}</p>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && code.length >= 4 && !submit2fa.isPending)
                      submit2fa.mutate();
                  }}
                  placeholder={t("authorize.codePlaceholder")}
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
                  {submit2fa.isPending ? t("common.verifying") : t("authorize.verifyCode")}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStep("password");
                    setCode("");
                  }}
                  className="text-slate-500 text-xs hover:text-slate-300"
                >
                  {t("authorize.backToPassword")}
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={closeModal}
              className="text-slate-500 text-sm hover:text-slate-300"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
