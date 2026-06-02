import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";

type Props = {
  userId: number;
  disabled?: boolean;
  size?: "sm" | "md";
};

export default function FetchCountButton({ userId, disabled, size = "md" }: Props) {
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);

  const fetchCount = useMutation({
    mutationFn: () => api.fetchPhotoCount(userId),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["photo-counts", userId] });
      if (result.already_running) {
        setFeedback("Sync in progress");
      } else if (result.ok) {
        setFeedback("Counting…");
      } else {
        setFeedback(result.message);
      }
      setTimeout(() => setFeedback(null), 5000);
    },
    onError: (err: Error) => {
      setFeedback(err.message);
      setTimeout(() => setFeedback(null), 5000);
    },
  });

  const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-4 py-2 text-sm";

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => fetchCount.mutate()}
        disabled={disabled || fetchCount.isPending}
        title="Scan iCloud library and index photos in the database (no download)"
        className={`bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg font-medium ${pad}`}
      >
        {fetchCount.isPending ? "Starting…" : "Fetch count"}
      </button>
      {feedback && <span className="text-xs text-violet-300">{feedback}</span>}
    </span>
  );
}
