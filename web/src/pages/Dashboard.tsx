import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <p className="text-slate-500 text-sm">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const qc = useQueryClient();
  const { data: stats, refetch } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
    refetchInterval: 15000,
  });
  const [events, setEvents] = useState<string[]>([]);
  const [dueFeedback, setDueFeedback] = useState<string | null>(null);

  const triggerDue = useMutation({
    mutationFn: () => api.triggerDueSyncs(),
    onSuccess: (r) => {
      setDueFeedback(r.message);
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["sync-runs"] });
      setTimeout(() => setDueFeedback(null), 5000);
    },
    onError: (e: Error) => {
      setDueFeedback(e.message);
      setTimeout(() => setDueFeedback(null), 5000);
    },
  });

  useEffect(() => {
    const es = new EventSource("/api/events/sync", { withCredentials: true });
    const onEvent = (e: MessageEvent) => {
      try {
        const d = JSON.parse(e.data);
        setEvents((prev) => [`${d.type} ${d.apple_id || ""}`, ...prev].slice(0, 20));
        if (d.type?.startsWith("sync.") || d.type?.startsWith("count.")) {
          refetch();
          qc.invalidateQueries({ queryKey: ["users"] });
          qc.invalidateQueries({ queryKey: ["sync-runs"] });
        }
      } catch {
        /* ignore */
      }
    };
    es.addEventListener("message", onEvent);
    es.onmessage = onEvent;
    return () => es.close();
  }, [refetch, qc]);

  if (!stats) return <div>Loading...</div>;

  return (
    <div>
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() => triggerDue.mutate()}
            disabled={triggerDue.isPending || stats.users_due_for_sync === 0}
            className="bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm"
          >
            {triggerDue.isPending
              ? "Starting…"
              : `Sync all due (${stats.users_due_for_sync})`}
          </button>
          {dueFeedback && (
            <span className="text-sm text-green-400">{dueFeedback}</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total users" value={stats.total_users} />
        <StatCard label="Enabled users" value={stats.enabled_users} />
        <StatCard label="Photos downloaded" value={stats.total_photos} />
        <StatCard label="Downloaded today" value={stats.downloaded_today} />
        <StatCard label="Active syncs" value={stats.active_syncs} />
        <StatCard label="Failed syncs" value={stats.failed_syncs} />
        <StatCard label="Due for sync" value={stats.users_due_for_sync} />
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-medium mb-3">Live events</h3>
          <ul className="text-sm text-slate-400 space-y-1 max-h-64 overflow-auto">
            {events.length === 0 && <li>No events yet</li>}
            {events.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="font-medium mb-3">Quick links</h3>
          <Link to="/users" className="text-sky-400 hover:underline block">
            Manage users — sync per account
          </Link>
          <Link to="/sync-runs" className="text-sky-400 hover:underline block mt-2">
            View sync history — retry failed runs
          </Link>
        </div>
      </div>
    </div>
  );
}
