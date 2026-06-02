import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, PhotoSource, TriggerSyncResult } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  source?: PhotoSource;
  label?: string;
  disabled?: boolean;
  title?: string;
  size?: "sm" | "md";
  onTriggered?: (result: TriggerSyncResult) => void;
};

export default function SyncNowButton({
  userId,
  source,
  label,
  disabled,
  title: titleOverride,
  size = "md",
  onTriggered,
}: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const toast = useToast();

  const sync = useMutation({
    mutationFn: () => api.triggerSync(userId, source),
    onSuccess: (result) => {
      onTriggered?.(result);
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["sync-runs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (result.already_running) {
        toast.warning(result.message || t("buttons.syncAlreadyRunning"));
      } else if (result.ok) {
        toast.success(result.message || t("buttons.syncStarted"));
      } else {
        toast.warning(result.message);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";
  const text =
    label ??
    (source === "icloud"
      ? t("buttons.syncIcloud")
      : source === "google_photos"
        ? t("buttons.syncGoogle")
        : t("buttons.syncAll"));

  return (
    <button
      type="button"
      onClick={() => sync.mutate()}
      disabled={disabled || sync.isPending}
      title={titleOverride ?? text}
      className={`bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium ${pad}`}
    >
      {sync.isPending ? t("common.starting") : text}
    </button>
  );
}
