import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useToast } from "./ToastProvider";

type Props = {
  userId: number;
  disabled?: boolean;
};

export default function ConnectGoogleButton({ userId, disabled }: Props) {
  const toast = useToast();
  const qc = useQueryClient();

  const start = useMutation({
    mutationFn: () => api.startGoogleOAuth(userId),
    onSuccess: (data) => {
      window.open(data.authorize_url, "_blank", "noopener,noreferrer");
      toast.info("Complete sign-in in the Google tab, then return here");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const disconnect = useMutation({
    mutationFn: () => api.disconnectGoogle(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["user", userId] });
      toast.success("Google Photos disconnected");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => start.mutate()}
        disabled={disabled || start.isPending}
        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium"
      >
        {start.isPending ? "Opening…" : "Connect Google Photos"}
      </button>
      <button
        type="button"
        onClick={() => disconnect.mutate()}
        disabled={disconnect.isPending}
        className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 px-3 py-2 rounded-lg text-sm"
      >
        Disconnect
      </button>
    </div>
  );
}
