import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api, PhotoSource } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  source: PhotoSource;
  disabled?: boolean;
  size?: "sm" | "md";
};

export default function FetchCountButton({ userId, source, disabled, size = "md" }: Props) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const toast = useToast();

  const fetchCount = useMutation({
    mutationFn: () => api.fetchPhotoCount(userId, source),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["photo-counts", userId] });
      if (result.already_running) {
        toast.warning(result.message || t("buttons.alreadyInProgress"));
      } else if (result.ok) {
        toast.info(result.message || t("buttons.countStarted"));
      } else {
        toast.warning(result.message);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";
  const label = source === "icloud" ? t("buttons.countIcloud") : t("buttons.countGoogle");
  const title = source === "icloud" ? t("buttons.countIcloudTitle") : t("buttons.countGoogleTitle");

  return (
    <button
      type="button"
      onClick={() => fetchCount.mutate()}
      disabled={disabled || fetchCount.isPending}
      title={title}
      className={`bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg font-medium ${pad}`}
    >
      {fetchCount.isPending ? t("common.starting") : label}
    </button>
  );
}
