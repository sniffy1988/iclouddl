import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, TriggerSyncResult } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  appleId?: string;
  disabled?: boolean;
  size?: "sm" | "md";
  onTriggered?: (result: TriggerSyncResult) => void;
};

export default function SyncNowButton({
  userId,
  appleId,
  disabled,
  size = "md",
  onTriggered,
}: Props) {
  const qc = useQueryClient();
  const toast = useToast();

  const sync = useMutation({
    mutationFn: () => api.triggerSync(userId),
    onSuccess: (result) => {
      onTriggered?.(result);
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["sync-runs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (result.already_running) {
        toast.warning("Sync already in progress");
      } else if (result.ok) {
        toast.success("Sync started");
      } else {
        toast.warning(result.message);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";

  return (
    <button
      type="button"
      onClick={() => sync.mutate()}
      disabled={disabled || sync.isPending}
      title={appleId ? `Sync ${appleId}` : "Start sync now"}
      className={`bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium ${pad}`}
    >
      {sync.isPending ? "Starting…" : "Sync now"}
    </button>
  );
}
