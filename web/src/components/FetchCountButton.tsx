import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  disabled?: boolean;
  size?: "sm" | "md";
};

export default function FetchCountButton({ userId, disabled, size = "md" }: Props) {
  const qc = useQueryClient();
  const toast = useToast();

  const fetchCount = useMutation({
    mutationFn: () => api.fetchPhotoCount(userId),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["photo-counts", userId] });
      if (result.already_running) {
        toast.warning("Sync already in progress");
      } else if (result.ok) {
        toast.info("Photo count started");
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
      onClick={() => fetchCount.mutate()}
      disabled={disabled || fetchCount.isPending}
      title="Scan iCloud library and index photos in the database (no download)"
      className={`bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg font-medium ${pad}`}
    >
      {fetchCount.isPending ? "Starting…" : "Fetch count"}
    </button>
  );
}
