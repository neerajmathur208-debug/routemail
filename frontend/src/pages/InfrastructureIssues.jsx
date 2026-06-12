import { useEffect, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  AlertCircle,
  Loader2,
  Play,
  Pause,
  RefreshCcw,
  Trash2,
  CheckCircle2,
} from "lucide-react";
import Sidebar from "../components/Sidebar";
import { Button } from "../components/ui/button";
import { api } from "../App";
import { toast } from "sonner";

const STATUS_PILL = {
  Paused: "bg-amber-100 text-amber-700",
  Risky: "bg-rose-100 text-rose-700",
  Errored: "bg-slate-100 text-slate-700",
};

export default function InfrastructureIssues({ user, setUser }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ counts: {}, paused: [], risky: [], errored: [] });
  const [selected, setSelected] = useState(new Set());
  const [running, setRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/infrastructure/issues");
      setData(res.data);
      setSelected(new Set());
    } catch (e) {
      toast.error("Failed to load issues");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => {
    const combined = [
      ...(data.paused || []).map((r) => ({ ...r, _kind: "Paused" })),
      ...(data.risky || []).map((r) => ({ ...r, _kind: "Risky" })),
      ...(data.errored || []).map((r) => ({ ...r, _kind: "Errored" })),
    ];
    // dedupe by account_id
    const seen = new Set();
    return combined.filter((r) => {
      if (seen.has(r.account_id)) return false;
      seen.add(r.account_id);
      return true;
    });
  }, [data]);

  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };
  const toggleAll = () => {
    if (selected.size === rows.length) setSelected(new Set());
    else setSelected(new Set(rows.map((r) => r.account_id)));
  };

  const bulk = async (action) => {
    if (selected.size === 0) {
      toast.error("Select at least one inbox");
      return;
    }
    if (action === "delete" && !window.confirm(`Permanently delete ${selected.size} inbox(es)? This cannot be undone.`)) {
      return;
    }
    setRunning(true);
    try {
      const res = await api.post("/infrastructure/issues/bulk", {
        action,
        account_ids: Array.from(selected),
      });
      const ok = res.data?.succeeded?.length || 0;
      const ko = res.data?.failed?.length || 0;
      if (ok > 0) toast.success(`${action}: ${ok} succeeded${ko ? `, ${ko} failed` : ""}`);
      if (ok === 0 && ko > 0) {
        toast.error(`${action}: ${ko} failed`);
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Bulk action failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex bg-slate-50 min-h-screen">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 lg:ml-64 p-6 lg:p-10 max-w-[1400px]">
        <div className="mb-6">
          <Link
            to="/infrastructure"
            className="text-sm text-slate-500 hover:text-slate-900 inline-flex items-center gap-1 mb-2"
            data-testid="issues-back-link"
          >
            <ArrowLeft size={14} /> Back to Infrastructure
          </Link>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <AlertCircle className="text-rose-600" size={26} strokeWidth={1.5} />
            Issues Dashboard
          </h1>
          <p className="text-sm text-slate-500 max-w-2xl mt-1">
            Every paused, risky, or errored inbox in one place. Select rows and apply bulk
            actions — Resume, Pause, Auto-Replace, or Delete.
          </p>
        </div>

        {/* Counts */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" data-testid="issues-counts">
          <CountCard label="Paused" value={data.counts.paused || 0} tone="amber" testid="issues-count-paused" />
          <CountCard label="Risky" value={data.counts.risky || 0} tone="rose" testid="issues-count-risky" />
          <CountCard label="Errored" value={data.counts.errored || 0} tone="slate" testid="issues-count-errored" />
          <CountCard label="Total" value={data.counts.total || 0} tone="slate" testid="issues-count-total" />
        </section>

        {/* Bulk action bar */}
        <section className="bg-white border border-slate-200 rounded-2xl p-3 mb-4 flex flex-wrap items-center gap-2" data-testid="issues-bulk-bar">
          <span className="text-xs text-slate-500 mr-2" data-testid="issues-selected-count">
            {selected.size} selected
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={selected.size === 0 || running}
            onClick={() => bulk("resume")}
            data-testid="issues-bulk-resume"
          >
            <Play size={14} className="mr-1.5" /> Resume
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={selected.size === 0 || running}
            onClick={() => bulk("pause")}
            data-testid="issues-bulk-pause"
          >
            <Pause size={14} className="mr-1.5" /> Pause
          </Button>
          <Button
            size="sm"
            disabled={selected.size === 0 || running}
            onClick={() => bulk("replace")}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="issues-bulk-replace"
          >
            <RefreshCcw size={14} className="mr-1.5" /> Auto-Replace
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={selected.size === 0 || running}
            onClick={() => bulk("delete")}
            className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
            data-testid="issues-bulk-delete"
          >
            <Trash2 size={14} className="mr-1.5" /> Delete
          </Button>
        </section>

        {/* Table */}
        <section className="bg-white border border-slate-200 rounded-2xl p-4">
          {loading ? (
            <div className="py-10 text-center text-sm text-slate-500" data-testid="issues-loading">
              <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
            </div>
          ) : rows.length === 0 ? (
            <div className="py-10 text-center text-sm text-slate-500 border border-dashed border-slate-200 rounded-lg" data-testid="issues-empty">
              <CheckCircle2 className="inline-block mr-2 text-emerald-500" size={16} />
              Everything looks healthy — no paused, risky or errored inboxes.
            </div>
          ) : (
            <div className="overflow-x-auto" data-testid="issues-table">
              <table className="min-w-full text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="text-left px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selected.size === rows.length && rows.length > 0}
                        onChange={toggleAll}
                        data-testid="issues-select-all"
                      />
                    </th>
                    <th className="text-left px-3 py-2 font-medium">Email</th>
                    <th className="text-left px-3 py-2 font-medium">Domain</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                    <th className="text-right px-3 py-2 font-medium">Active</th>
                    <th className="text-left px-3 py-2 font-medium">Last Activity</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.account_id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                      data-testid={`issues-row-${r.account_id}`}
                    >
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={selected.has(r.account_id)}
                          onChange={() => toggle(r.account_id)}
                          data-testid={`issues-select-${r.account_id}`}
                        />
                      </td>
                      <td className="px-3 py-2 font-medium text-slate-900">{r.email}</td>
                      <td className="px-3 py-2 text-slate-600">{r.domain}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            STATUS_PILL[r._kind] || "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {r._kind}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                        {r.active_campaign_count}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {r.last_activity_at ? r.last_activity_at.slice(0, 10) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function CountCard({ label, value, tone = "slate", testid }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50/60 text-slate-900",
    rose: "border-rose-200 bg-rose-50/60 text-rose-800",
    amber: "border-amber-200 bg-amber-50/60 text-amber-800",
  };
  return (
    <div
      className={`border rounded-lg px-3 py-2 ${tones[tone] || tones.slate}`}
      data-testid={testid}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}
