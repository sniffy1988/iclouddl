type Variant = "auth" | "activity";

const AUTH_STYLES: Record<string, string> = {
  authorized: "bg-emerald-900/50 text-emerald-400",
  reauth_required: "bg-amber-900/50 text-amber-400",
  expired: "bg-red-900/50 text-red-400",
  not_authorized: "bg-slate-800 text-slate-400",
};

const AUTH_LABELS: Record<string, string> = {
  authorized: "Authorized",
  reauth_required: "Re-auth required",
  expired: "Session expired",
  not_authorized: "Not authorized",
};

const ACTIVITY_STYLES: Record<string, string> = {
  completed: "bg-green-900/50 text-green-400",
  count_ready: "bg-green-900/50 text-green-400",
  counting: "bg-sky-900/50 text-sky-400",
  syncing: "bg-sky-900/50 text-sky-400",
  queued: "bg-sky-900/50 text-sky-400",
  failed: "bg-red-900/50 text-red-400",
  count_failed: "bg-red-900/50 text-red-400",
  idle: "bg-slate-800 text-slate-400",
};

const ACTIVITY_LABELS: Record<string, string> = {
  completed: "Sync done",
  count_ready: "Indexed",
  counting: "Indexing",
  syncing: "Syncing",
  queued: "Queued",
  failed: "Failed",
  count_failed: "Index failed",
  idle: "Idle",
};

type Props = {
  variant: Variant;
  status: string;
  className?: string;
};

export default function StatusPill({ variant, status, className = "" }: Props) {
  const styles = variant === "auth" ? AUTH_STYLES : ACTIVITY_STYLES;
  const labels = variant === "auth" ? AUTH_LABELS : ACTIVITY_LABELS;
  const style = styles[status] ?? "bg-slate-800 text-slate-400";
  const label = labels[status] ?? status.replace(/_/g, " ");

  return (
    <span
      className={`px-2 py-0.5 rounded text-xs whitespace-nowrap capitalize ${style} ${className}`}
    >
      {label}
    </span>
  );
}
