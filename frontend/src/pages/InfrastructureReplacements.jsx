import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  RefreshCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Wand2,
  User as UserIcon,
} from "lucide-react";
import Sidebar from "../components/Sidebar";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { api } from "../App";
import { toast } from "sonner";

function StatusPillCmp({ status }) {
  if (status === "completed")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
        <CheckCircle2 size={12} /> Completed
      </span>
    );
  if (status === "no_candidate")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
        <AlertTriangle size={12} /> No candidate
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-rose-100 text-rose-700">
      <XCircle size={12} /> {status || "failed"}
    </span>
  );
}

export default function InfrastructureReplacements({ user, setUser }) {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [statusFilter, setStatusFilter] = useState("__all__");
  const [triggerFilter, setTriggerFilter] = useState("__all__");
  const [scanning, setScanning] = useState(false);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== "__all__") params.set("status", statusFilter);
      if (triggerFilter !== "__all__") params.set("triggered_by", triggerFilter);
      const res = await api.get(`/infrastructure/replacements?${params.toString()}`);
      setItems(res.data?.items || []);
      setCounts(res.data?.counts || {});
    } catch (e) {
      toast.error("Failed to load replacement history");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, triggerFilter]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const runAutoScan = async () => {
    setScanning(true);
    try {
      const res = await api.post("/infrastructure/replacements/auto-scan");
      const c = res.data?.completed?.length || 0;
      const n = res.data?.no_candidate?.length || 0;
      if (c === 0 && n === 0) toast.message("No at-risk inboxes found");
      else
        toast.success(
          `Auto-scan complete — ${c} replaced` + (n ? `, ${n} unresolved (no free candidate)` : "")
        );
      fetchHistory();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Auto-scan failed");
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="flex bg-slate-50 min-h-screen">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 lg:ml-64 p-6 lg:p-10 max-w-[1400px]">
        <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <Link
              to="/infrastructure"
              className="text-sm text-slate-500 hover:text-slate-900 inline-flex items-center gap-1 mb-2"
              data-testid="back-to-infra"
            >
              <ArrowLeft size={14} /> Back to Infrastructure
            </Link>
            <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
              <RefreshCcw className="text-violet-600" size={26} strokeWidth={1.5} />
              Replacement History
            </h1>
            <p className="text-sm text-slate-500 max-w-2xl mt-1">
              Every automatic and manual inbox swap. Replacements are sourced from healthy,
              currently-unassigned inboxes — cross-domain first.
            </p>
          </div>
          <Button
            onClick={runAutoScan}
            disabled={scanning}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="rep-auto-scan-btn"
          >
            {scanning ? (
              <Loader2 className="mr-2 animate-spin" size={16} />
            ) : (
              <Wand2 className="mr-2" size={16} />
            )}
            Scan & Auto-Replace
          </Button>
        </div>

        {/* Counts */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6" data-testid="rep-counts">
          <CountCard label="Total entries" value={items.length} tone="slate" testid="rep-count-total" />
          <CountCard label="Completed" value={counts.completed || 0} tone="emerald" testid="rep-count-completed" />
          <CountCard label="No candidate" value={counts.no_candidate || 0} tone="amber" testid="rep-count-nocand" />
          <CountCard label="Automatic" value={counts.by_auto || 0} tone="violet" testid="rep-count-auto" />
        </section>

        {/* Filters */}
        <section className="bg-white border border-slate-200 rounded-2xl p-4 mb-4">
          <div className="flex items-end flex-wrap gap-3">
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Status</Label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-44" data-testid="rep-filter-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="no_candidate">No candidate</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Triggered by</Label>
              <Select value={triggerFilter} onValueChange={setTriggerFilter}>
                <SelectTrigger className="w-44" data-testid="rep-filter-trigger">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All</SelectItem>
                  <SelectItem value="auto">Auto</SelectItem>
                  <SelectItem value="manual">Manual</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="outline"
              onClick={() => {
                setStatusFilter("__all__");
                setTriggerFilter("__all__");
              }}
              data-testid="rep-filter-reset"
            >
              Reset
            </Button>
          </div>
        </section>

        {/* Table */}
        <section className="bg-white border border-slate-200 rounded-2xl p-4">
          {loading ? (
            <div className="py-10 text-center text-sm text-slate-500" data-testid="rep-loading">
              <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
            </div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-sm text-slate-500 border border-dashed border-slate-200 rounded-lg" data-testid="rep-empty">
              No replacement history yet. Trigger an auto-scan or replace an inbox from the
              Infrastructure page.
            </div>
          ) : (
            <div className="overflow-x-auto" data-testid="rep-table">
              <table className="min-w-full text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">When</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                    <th className="text-left px-3 py-2 font-medium">Replaced</th>
                    <th className="text-left px-3 py-2 font-medium">Replacement</th>
                    <th className="text-left px-3 py-2 font-medium">Reason</th>
                    <th className="text-left px-3 py-2 font-medium">Trigger</th>
                    <th className="text-right px-3 py-2 font-medium">Camp/Drip swapped</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr
                      key={r.replacement_id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                      data-testid={`rep-row-${r.replacement_id}`}
                    >
                      <td className="px-3 py-2 text-slate-600 whitespace-nowrap">
                        {r.created_at ? r.created_at.replace("T", " ").slice(0, 19) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        <StatusPillCmp status={r.status} />
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-slate-900">{r.replaced_email}</div>
                        <div className="text-xs text-slate-500">
                          {r.replaced_domain} · was {r.replaced_status}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        {r.replacement_email ? (
                          <div>
                            <div className="font-medium text-slate-900">{r.replacement_email}</div>
                            <div className="text-xs text-slate-500">
                              {r.replacement_domain}
                              {r.cross_domain ? (
                                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-violet-50 text-violet-700 text-[10px]">
                                  cross-domain
                                </span>
                              ) : null}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-600">{r.reason || "—"}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                            r.triggered_by === "auto"
                              ? "bg-violet-100 text-violet-700"
                              : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {r.triggered_by === "auto" ? <Wand2 size={11} /> : <UserIcon size={11} />}
                          {r.triggered_by}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                        {(r.campaigns_swapped?.length || 0)} / {(r.drips_swapped?.length || 0)}
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
    emerald: "border-emerald-200 bg-emerald-50/60 text-emerald-800",
    amber: "border-amber-200 bg-amber-50/60 text-amber-800",
    violet: "border-violet-200 bg-violet-50/60 text-violet-800",
  };
  return (
    <div
      className={`border rounded-lg px-3 py-2 ${tones[tone] || tones.slate}`}
      data-testid={testid}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-xl font-bold tabular-nums">{value}</div>
    </div>
  );
}
