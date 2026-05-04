import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Download,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  Mail,
  AlertCircle,
  ShieldOff,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { Progress } from "../components/ui/progress";
import Sidebar from "../components/Sidebar";
import { api, BACKEND_URL } from "../App";
import { toast } from "sonner";

export default function CampaignLogs({ user, setUser }) {
  const navigate = useNavigate();
  const { campaignId } = useParams();
  const [campaign, setCampaign] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 50;

  const fetchCampaign = useCallback(async () => {
    try {
      const response = await api.get(`/campaigns/${campaignId}`);
      setCampaign(response.data);
    } catch (error) {
      console.error("Failed to fetch campaign:", error);
      toast.error("Failed to load campaign");
      navigate("/campaign");
    }
  }, [campaignId, navigate]);

  const fetchLogs = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.append("skip", page * limit);
      params.append("limit", limit);
      if (statusFilter) params.append("status", statusFilter);
      if (searchQuery) params.append("search", searchQuery);

      const response = await api.get(`/campaigns/${campaignId}/logs?${params.toString()}`);
      setLogs(response.data.logs);
      setTotal(response.data.total);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    } finally {
      setLoading(false);
    }
  }, [campaignId, page, statusFilter, searchQuery]);

  useEffect(() => {
    fetchCampaign();
  }, [fetchCampaign]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleExport = () => {
    window.open(`${BACKEND_URL}/api/campaigns/${campaignId}/logs/export`, "_blank");
  };

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(0);
    fetchLogs();
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "sent":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
            <CheckCircle2 size={12} /> Sent
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
            <XCircle size={12} /> Failed
          </span>
        );
      case "suppressed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-700">
            <ShieldOff size={12} /> Suppressed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
            <Clock size={12} /> Pending
          </span>
        );
    }
  };

  if (loading && !campaign) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 p-8">
          <div className="animate-pulse">Loading...</div>
        </main>
      </div>
    );
  }

  const sentCount = campaign?.sent_count || 0;
  const failedCount = campaign?.failed_count || 0;
  const totalEmails = campaign?.total_emails || 0;
  const failureRate = totalEmails > 0 ? ((failedCount / totalEmails) * 100).toFixed(1) : 0;
  const successRate = totalEmails > 0 ? ((sentCount / totalEmails) * 100).toFixed(1) : 0;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/campaign")}
              data-testid="back-btn"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex-1">
              <h1 className="font-heading font-extrabold text-2xl text-slate-900">
                {campaign?.name || "Campaign"} - Sending Log
              </h1>
              <p className="text-slate-500 mt-1">{campaign?.subject}</p>
            </div>
            <Button variant="outline" onClick={fetchLogs} data-testid="refresh-btn">
              <RefreshCw size={16} className="mr-2" />
              Refresh
            </Button>
            <Button onClick={handleExport} className="bg-electric-blue hover:bg-blue-700" data-testid="export-btn">
              <Download size={16} className="mr-2" />
              Export CSV
            </Button>
          </div>

          {/* Stats Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <Mail size={16} />
                <span className="text-sm">Total Emails</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{totalEmails}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-green-600 mb-1">
                <CheckCircle2 size={16} />
                <span className="text-sm">Sent</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{sentCount}</p>
              <p className="text-xs text-green-600">{successRate}%</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-red-500 mb-1">
                <XCircle size={16} />
                <span className="text-sm">Failed</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{failedCount}</p>
              <p className="text-xs text-red-500">{failureRate}%</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <Clock size={16} />
                <span className="text-sm">Remaining</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">
                {totalEmails - sentCount - failedCount}
              </p>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="bg-white border border-slate-200 rounded-md p-4 mb-6">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-slate-500">Progress</span>
              <span className="font-medium text-slate-900">
                {sentCount + failedCount} / {totalEmails}
              </span>
            </div>
            <Progress value={((sentCount + failedCount) / totalEmails) * 100} className="h-2" />
          </div>

          {/* Filters */}
          <div className="bg-white border border-slate-200 rounded-md p-4 mb-6">
            <form onSubmit={handleSearch} className="flex gap-4">
              <div className="flex-1 relative">
                <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  placeholder="Search by email..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                  data-testid="search-input"
                />
              </div>
              <Select value={statusFilter || "all"} onValueChange={(v) => { setStatusFilter(v === "all" ? "" : v); setPage(0); }}>
                <SelectTrigger className="w-40" data-testid="status-filter">
                  <SelectValue placeholder="All Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="sent">Sent</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="suppressed">Suppressed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" variant="outline">Search</Button>
            </form>
          </div>

          {/* Logs Table */}
          <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Recipient Email</TableHead>
                  <TableHead>Sent From</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Sent At</TableHead>
                  <TableHead>Error Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.length > 0 ? (
                  logs.map((log) => (
                    <TableRow key={log.queue_id}>
                      <TableCell className="font-mono text-sm">{log.recipient_email}</TableCell>
                      <TableCell className="text-sm text-slate-500">
                        {log.account_email || "-"}
                      </TableCell>
                      <TableCell>{getStatusBadge(log.status)}</TableCell>
                      <TableCell className="text-sm text-slate-500">
                        {log.sent_at ? new Date(log.sent_at).toLocaleString() : "-"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {log.error_message ? (
                          <span className="text-red-600 flex items-center gap-1">
                            <AlertCircle size={14} />
                            {log.error_message}
                          </span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-slate-500">
                      No logs found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>

            {/* Pagination */}
            {total > limit && (
              <div className="flex items-center justify-between p-4 border-t border-slate-200">
                <p className="text-sm text-slate-500">
                  Showing {page * limit + 1} - {Math.min((page + 1) * limit, total)} of {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(Math.max(0, page - 1))}
                    disabled={page === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(page + 1)}
                    disabled={(page + 1) * limit >= total}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
