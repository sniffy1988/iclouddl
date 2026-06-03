import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  disabled?: boolean;
};

export default function DisconnectIcloudButton({ userId, disabled }: Props) {
  const { t } = useTranslation();
  const toast = useToast();
  const qc = useQueryClient();

  const disconnect = useMutation({
    mutationFn: () => api.disconnectIcloud(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["challenge", userId] });
      toast.success(t("icloud.disconnected"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <button
      type="button"
      onClick={() => disconnect.mutate()}
      disabled={disabled || disconnect.isPending}
      className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-2 rounded-lg text-sm"
    >
      {disconnect.isPending ? t("common.starting") : t("buttons.disconnect")}
    </button>
  );
}
