import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, PhotoSource } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  source: PhotoSource;
  disabled?: boolean;
  size?: "sm" | "md";
};

export default function FetchCountButton({ userId, source, disabled, size = "md" }: Props) {
  const qc = useQueryClient();
  const toast = useToast();

  const fetchCount = useMutation({
    mutationFn: () => api.fetchPhotoCount(userId, source),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["photo-counts", userId] });
      if (result.already_running) {
        toast.warning(result.message || "Already in progress");
      } else if (result.ok) {
        toast.info(result.message || "Photo count started");
      } else {
        toast.warning(result.message);
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";
  const label = source === "icloud" ? "Count iCloud" : "Count Google";

  return (
    <button
      type="button"
      onClick={() => fetchCount.mutate()}
      disabled={disabled || fetchCount.isPending}
      title={`Index ${source} metadata (no download)`}
      className={`bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg font-medium ${pad}`}
    >
      {fetchCount.isPending ? "Starting…" : label}
    </button>
  );
}
