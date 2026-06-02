import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  googleAuthorized?: boolean;
  googleNeedsAuth?: boolean;
  disabled?: boolean;
};

export default function ConnectGoogleButton({
  userId,
  googleAuthorized = false,
  googleNeedsAuth = false,
  disabled,
}: Props) {
  const { t } = useTranslation();
  const toast = useToast();
  const qc = useQueryClient();
  const isConnected = googleAuthorized && !googleNeedsAuth;

  const start = useMutation({
    mutationFn: () => api.startGoogleOAuth(userId),
    onSuccess: (data) => {
      window.open(data.authorize_url, "_blank", "noopener,noreferrer");
      toast.info(t("google.completeSignIn"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const disconnect = useMutation({
    mutationFn: () => api.disconnectGoogle(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      toast.success(t("google.disconnected"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="flex flex-wrap gap-2">
      {!isConnected && (
        <button
          type="button"
          onClick={() => start.mutate()}
          disabled={disabled || start.isPending}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium"
        >
          {start.isPending ? t("common.opening") : t("buttons.connectGoogle")}
        </button>
      )}
      {(isConnected || googleNeedsAuth) && (
        <button
          type="button"
          onClick={() => start.mutate()}
          disabled={disabled || start.isPending}
          className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-2 rounded-lg text-sm"
        >
          {start.isPending ? t("common.opening") : t("buttons.reconnectGoogle")}
        </button>
      )}
      {(isConnected || googleNeedsAuth) && (
        <button
          type="button"
          onClick={() => disconnect.mutate()}
          disabled={disconnect.isPending}
          className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-2 rounded-lg text-sm"
        >
          {t("buttons.disconnect")}
        </button>
      )}
    </div>
  );
}
