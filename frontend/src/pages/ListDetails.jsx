import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Users,
  Calendar,
  FileText,
  Tag,
  Edit2,
  Check,
  X,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

export default function ListDetails({ user, setUser }) {
  const navigate = useNavigate();
  const { listId } = useParams();
  const [list, setList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

  const fetchList = useCallback(async () => {
    try {
      const response = await api.get(`/lists/${listId}`);
      setList(response.data);
      setEditName(response.data.name);
    } catch (error) {
      console.error("Failed to fetch list:", error);
      toast.error("Failed to load list details");
      navigate("/email-lists");
    } finally {
      setLoading(false);
    }
  }, [listId, navigate]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const handleSaveRename = async () => {
    if (!editName.trim()) {
      toast.error("List name cannot be empty");
      return;
    }

    try {
      await api.put(`/lists/${listId}`, { name: editName.trim() });
      toast.success("List renamed successfully");
      setIsEditing(false);
      fetchList();
    } catch (error) {
      toast.error("Failed to rename list");
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 p-8">
          <div className="animate-pulse">Loading...</div>
        </main>
      </div>
    );
  }

  if (!list) {
    return null;
  }

  const previewEmails = list.emails?.slice(0, 20) || [];
  const columnHeaders = list.column_headers || ["email"];

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
              onClick={() => navigate("/email-lists")}
              data-testid="back-btn"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex-1">
              {isEditing ? (
                <div className="flex items-center gap-2">
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="h-10 text-xl font-bold w-80"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleSaveRename();
                      if (e.key === "Escape") {
                        setIsEditing(false);
                        setEditName(list.name);
                      }
                    }}
                    data-testid="edit-name-input"
                  />
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={handleSaveRename}
                    data-testid="save-name-btn"
                  >
                    <Check size={20} className="text-green-600" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => {
                      setIsEditing(false);
                      setEditName(list.name);
                    }}
                    data-testid="cancel-name-btn"
                  >
                    <X size={20} className="text-slate-400" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <h1 className="font-heading font-extrabold text-2xl text-slate-900">
                    {list.name}
                  </h1>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsEditing(true)}
                    data-testid="edit-name-btn"
                  >
                    <Edit2 size={18} className="text-slate-400" />
                  </Button>
                </div>
              )}
              {list.original_filename && list.original_filename !== list.name && (
                <p className="text-slate-500 text-sm mt-1">
                  Original file: {list.original_filename}
                </p>
              )}
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <Users size={16} />
                <span className="text-sm">Total Contacts</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{list.valid_emails || 0}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <Calendar size={16} />
                <span className="text-sm">Date Uploaded</span>
              </div>
              <p className="text-sm font-medium text-slate-900">{formatDate(list.created_at)}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <div className="flex items-center gap-2 text-slate-500 mb-1">
                <FileText size={16} />
                <span className="text-sm">Original Rows</span>
              </div>
              <p className="text-2xl font-bold text-slate-900">{list.total_rows || 0}</p>
              {list.total_rows !== list.valid_emails && (
                <p className="text-xs text-slate-400">
                  {(list.total_rows || 0) - (list.valid_emails || 0)} invalid/duplicates removed
                </p>
              )}
            </div>
          </div>

          {/* Column Headers / Variables */}
          <div className="bg-white border border-slate-200 rounded-md p-4 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Tag size={16} className="text-slate-500" />
              <h2 className="font-semibold text-slate-900">Available Variables</h2>
            </div>
            <p className="text-sm text-slate-500 mb-3">
              Use these variables in your email subject and body for personalization:
            </p>
            <div className="flex flex-wrap gap-2">
              {columnHeaders.map((header) => (
                <Badge
                  key={header}
                  className="bg-blue-100 text-blue-700 hover:bg-blue-200 cursor-default"
                >
                  {`{{${header}}}`}
                </Badge>
              ))}
            </div>
          </div>

          {/* Preview Table */}
          <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
            <div className="p-4 border-b border-slate-200">
              <h2 className="font-semibold text-slate-900">
                Contact Preview
                {list.emails?.length > 20 && (
                  <span className="text-sm font-normal text-slate-500 ml-2">
                    (showing first 20 of {list.emails.length})
                  </span>
                )}
              </h2>
            </div>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">#</TableHead>
                    {columnHeaders.map((header) => (
                      <TableHead key={header} className="whitespace-nowrap">
                        {header}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewEmails.length > 0 ? (
                    previewEmails.map((row, index) => (
                      <motion.tr
                        key={index}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: index * 0.02 }}
                        className="border-b border-slate-100"
                      >
                        <TableCell className="text-slate-400 text-sm">{index + 1}</TableCell>
                        {columnHeaders.map((header) => (
                          <TableCell key={header} className="font-mono text-sm whitespace-nowrap">
                            {row[header] || "-"}
                          </TableCell>
                        ))}
                      </motion.tr>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell
                        colSpan={columnHeaders.length + 1}
                        className="text-center py-8 text-slate-500"
                      >
                        No contacts in this list
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          {/* Back Button */}
          <div className="mt-6">
            <Button
              variant="outline"
              onClick={() => navigate("/email-lists")}
              data-testid="back-to-lists-btn"
            >
              <ArrowLeft size={16} className="mr-2" />
              Back to Lists
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
