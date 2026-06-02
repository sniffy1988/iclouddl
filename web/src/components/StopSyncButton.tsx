import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, PhotoSource } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  source?: PhotoSource;
  disabled?: boolean;
  size?: "sm" | "md";
};

export default function StopSyncButton({ userId, source, disabled, size = "md" }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const toast = useToast();

  const cancel = useMutation({
    mutationFn: () => api.cancelSync(userId, source),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["sync-runs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (result.ok) toast.info(result.message);
      else toast.warning(result.message);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";

  return (
    <button
      type="button"
      onClick={() => cancel.mutate()}
      disabled={disabled || cancel.isPending}
      title={t("buttons.stopSyncTitle")}
      className={`bg-red-900/70 hover:bg-red-800 disabled:opacity-50 rounded-lg font-medium text-red-100 ${pad}`}
    >
      {cancel.isPending ? t("common.stopping") : t("buttons.stopSync")}
    </button>
  );
}
