import { useState } from "react";
import axios from "axios";
import { Download, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "./ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Checkbox } from "./ui/checkbox";
import { toast } from "sonner";

const STATUS_OPTIONS = ["draft", "scheduled", "running", "paused", "completed"];

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Excel campaign-report exporter. Drop this anywhere — it owns its own dialog,
 * the date / type / status filters, and the actual HTTP call. The parent only
 * controls open/close via `open` + `onOpenChange`, and optionally locks the
 * `campaign_type` field via `lockType` (e.g. `"drip"` on the Drip Campaigns
 * page so the user can't accidentally swap to regular campaigns from there).
 */
export default function ExportReportDialog({
  open,
  onOpenChange,
  lockType = null, // "all" | "campaigns" | "drip" | null (user-controlled)
  title = "Export Campaign Report",
}) {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [campaignType, setCampaignType] = useState(lockType || "all");
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [busy, setBusy] = useState(false);

  const toggleStatus = (s) => {
    setSelectedStatuses((prev) =>
      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
    );
  };

  const handleExport = async () => {
    if (fromDate && toDate && fromDate > toDate) {
      toast.error("From Date must be on or before To Date");
      return;
    }
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (fromDate) params.append("from_date", fromDate);
      if (toDate) params.append("to_date", toDate);
      params.append("campaign_type", lockType || campaignType);
      if (selectedStatuses.length) params.append("status", selectedStatuses.join(","));

      const res = await axios.get(`${API}/reports/export?${params.toString()}`, {
        withCredentials: true,
        responseType: "blob",
      });

      // Extract filename from Content-Disposition or fall back
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const fname = m ? m[1] : `RouteMail_Campaign_Report_${new Date().toISOString().slice(0, 10)}.xlsx`;

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Report downloaded");
      onOpenChange(false);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Export failed";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]" data-testid="export-report-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="text-violet-600" size={20} /> {title}
          </DialogTitle>
          <DialogDescription>
            Export campaign performance to an Excel (.xlsx) workbook. Optional filters
            below scope the report.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="export-from-date">From Date</Label>
              <Input
                id="export-from-date"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                data-testid="export-from-date"
                className="mt-1.5"
              />
            </div>
            <div>
              <Label htmlFor="export-to-date">To Date</Label>
              <Input
                id="export-to-date"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                data-testid="export-to-date"
                className="mt-1.5"
              />
            </div>
          </div>

          {!lockType && (
            <div>
              <Label>Campaign Type</Label>
              <Select value={campaignType} onValueChange={setCampaignType}>
                <SelectTrigger className="mt-1.5" data-testid="export-campaign-type-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="campaigns">Campaigns Only</SelectItem>
                  <SelectItem value="drip">Drip Campaigns Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <div>
            <Label className="mb-1.5 block">Status</Label>
            <div className="flex flex-wrap gap-3 mt-2" data-testid="export-status-row">
              {STATUS_OPTIONS.map((s) => (
                <label
                  key={s}
                  className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer select-none"
                >
                  <Checkbox
                    checked={selectedStatuses.includes(s)}
                    onCheckedChange={() => toggleStatus(s)}
                    data-testid={`export-status-${s}`}
                  />
                  <span className="capitalize">{s}</span>
                </label>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Leave all unchecked to include every status.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
            data-testid="export-report-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={handleExport}
            disabled={busy}
            className="bg-violet-600 hover:bg-violet-700 text-white"
            data-testid="export-report-confirm"
          >
            {busy ? (
              <Loader2 className="mr-2 animate-spin" size={16} />
            ) : (
              <Download className="mr-2" size={16} />
            )}
            Export to Excel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
