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
  Download,
  Pencil,
  Plus,
  Trash2,
  Search,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import Sidebar from "../components/Sidebar";
import { api, API } from "../App";
import { toast } from "sonner";

const EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

export default function ListDetails({ user, setUser }) {
  const navigate = useNavigate();
  const { listId } = useParams();
  const [list, setList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");

  // Record edit dialog state
  const [editRow, setEditRow] = useState(null); // { original_email, data }
  const [editValues, setEditValues] = useState({});
  const [savingRow, setSavingRow] = useState(false);

  // Add record dialog state
  const [addOpen, setAddOpen] = useState(false);
  const [addValues, setAddValues] = useState({});
  const [addingRow, setAddingRow] = useState(false);

  // Delete record state
  const [deleteRow, setDeleteRow] = useState(null);

  // Phase Batch-1 — partial-match search across all columns
  const [searchQuery, setSearchQuery] = useState("");

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

  const handleOpenEditRow = (row) => {
    setEditRow({ original_email: row.email || "" });
    setEditValues({ ...row });
  };

  const handleSaveRow = async () => {
    if (!editValues.email || !EMAIL_RE.test(String(editValues.email).trim())) {
      toast.error("Please enter a valid email address");
      return;
    }
    setSavingRow(true);
    try {
      await api.put(`/lists/${listId}/record`, {
        original_email: editRow.original_email,
        data: editValues,
      });
      toast.success("Contact updated");
      setEditRow(null);
      setEditValues({});
      fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to update contact");
    } finally {
      setSavingRow(false);
    }
  };

  const handleOpenAdd = () => {
    const seed = {};
    (list?.column_headers || ["email"]).forEach((h) => { seed[h] = ""; });
    setAddValues(seed);
    setAddOpen(true);
  };

  const handleAddRecord = async () => {
    const email = String(addValues.email || "").trim();
    if (!email || !EMAIL_RE.test(email)) {
      toast.error("Please enter a valid email address");
      return;
    }
    setAddingRow(true);
    try {
      await api.post(`/lists/${listId}/records`, { data: addValues });
      toast.success("Contact added");
      setAddOpen(false);
      setAddValues({});
      fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add contact");
    } finally {
      setAddingRow(false);
    }
  };

  const handleDeleteRow = async () => {
    if (!deleteRow) return;
    try {
      await api.delete(`/lists/${listId}/records`, { data: { email: deleteRow.email } });
      toast.success("Contact removed");
      setDeleteRow(null);
      fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to remove contact");
    }
  };

  const handleDownload = () => {
    window.open(`${API}/lists/${listId}/export`, "_blank");
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

  if (!list) return null;

  const allEmails = list.emails || [];
  const searchTokens = (searchQuery || "")
    .toLowerCase()
    .split(/\s+/)
    .map((t) => t.trim())
    .filter(Boolean);

  // Phase Batch-1 — partial substring search across email + every other
  // column header value (first_name, last_name, company, phone, linkedin etc.).
  const emails = searchTokens.length === 0
    ? allEmails
    : allEmails.filter((row) => {
        const haystack = Object.values(row || {})
          .filter((v) => v !== null && v !== undefined)
          .map((v) => String(v).toLowerCase())
          .join(" ");
        // ALL tokens must match somewhere — supports "john acme" → row that has both
        return searchTokens.every((t) => haystack.includes(t));
      });
  let columnHeaders = list.column_headers || ["email"];
  if (!columnHeaders.includes("email")) columnHeaders = ["email", ...columnHeaders];

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
                  <Button size="icon" variant="ghost" onClick={handleSaveRename} data-testid="save-name-btn">
                    <Check size={20} className="text-green-600" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => { setIsEditing(false); setEditName(list.name); }}
                    data-testid="cancel-name-btn"
                  >
                    <X size={20} className="text-slate-400" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <h1 className="font-heading font-extrabold text-2xl text-slate-900">{list.name}</h1>
                  <Button variant="ghost" size="icon" onClick={() => setIsEditing(true)} data-testid="edit-name-btn">
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
            <Button
              variant="outline"
              onClick={handleDownload}
              data-testid="list-download-btn"
            >
              <Download size={16} className="mr-2" /> Download CSV
            </Button>
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

          {/* Variables */}
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
                  {`{${header}}`}
                </Badge>
              ))}
            </div>
          </div>

          {/* Contacts Table — all rows, editable */}
          <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold text-slate-900 whitespace-nowrap">
                Contacts{" "}
                <span className="text-sm font-normal text-slate-500 ml-2" data-testid="list-result-count">
                  ({allEmails.length.toLocaleString()} records
                  {searchTokens.length > 0 && (
                    <>, <span className="text-blue-700">{emails.length.toLocaleString()} matched</span></>
                  )})
                </span>
              </h2>
              <div className="flex items-center gap-2 flex-1 min-w-[260px] max-w-md ml-auto">
                <div className="relative flex-1">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <Input
                    placeholder="Search email, name, company, phone, LinkedIn…"
                    className="pl-9"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    data-testid="list-search-input"
                  />
                </div>
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSearchQuery("")}
                    data-testid="list-search-clear"
                    className="h-8"
                  >
                    Clear
                  </Button>
                )}
              </div>
              <Button
                size="sm"
                onClick={handleOpenAdd}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="list-add-record-btn"
              >
                <Plus size={14} className="mr-1.5" /> Add record
              </Button>
            </div>
            <div className="overflow-x-auto max-h-[60vh] overflow-y-auto">
              <Table>
                <TableHeader className="sticky top-0 bg-white z-10">
                  <TableRow>
                    <TableHead className="w-12">#</TableHead>
                    {columnHeaders.map((header) => (
                      <TableHead key={header} className="whitespace-nowrap">{header}</TableHead>
                    ))}
                    <TableHead className="w-28 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {emails.length > 0 ? (
                    emails.map((row, index) => (
                      <motion.tr
                        key={`${row.email}-${index}`}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: Math.min(index, 20) * 0.01 }}
                        className="border-b border-slate-100"
                        data-testid={`list-row-${row.email}`}
                      >
                        <TableCell className="text-slate-400 text-sm">{index + 1}</TableCell>
                        {columnHeaders.map((header) => (
                          <TableCell key={header} className="font-mono text-sm whitespace-nowrap">
                            {row[header] || "-"}
                          </TableCell>
                        ))}
                        <TableCell className="text-right">
                          <div className="inline-flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleOpenEditRow(row)}
                              data-testid={`list-edit-row-${row.email}`}
                              className="h-8 w-8"
                              title="Edit"
                            >
                              <Pencil size={14} />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteRow(row)}
                              data-testid={`list-delete-row-${row.email}`}
                              className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50"
                              title="Delete"
                            >
                              <Trash2 size={14} />
                            </Button>
                          </div>
                        </TableCell>
                      </motion.tr>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell
                        colSpan={columnHeaders.length + 2}
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

        {/* Edit Record Dialog */}
        <Dialog open={!!editRow} onOpenChange={(o) => !o && setEditRow(null)}>
          <DialogContent data-testid="list-edit-row-dialog">
            <DialogHeader>
              <DialogTitle>Edit contact</DialogTitle>
              <DialogDescription>
                Update fields for this contact. Email format will be validated on save.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
              {columnHeaders.map((header) => (
                <div key={header}>
                  <Label htmlFor={`edit-field-${header}`} className="capitalize">
                    {header}
                    {header === "email" && <span className="text-red-500 ml-1">*</span>}
                  </Label>
                  <Input
                    id={`edit-field-${header}`}
                    data-testid={`list-edit-field-${header}`}
                    value={editValues[header] || ""}
                    onChange={(e) => setEditValues({ ...editValues, [header]: e.target.value })}
                    className="mt-1.5"
                    type={header === "email" ? "email" : "text"}
                  />
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditRow(null)}>Cancel</Button>
              <Button
                onClick={handleSaveRow}
                disabled={savingRow}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="list-edit-row-save-btn"
              >
                {savingRow ? "Saving…" : "Save changes"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Add Record Dialog */}
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent data-testid="list-add-record-dialog">
            <DialogHeader>
              <DialogTitle>Add a contact</DialogTitle>
              <DialogDescription>
                Manually add a single contact to this list. Email is required and will be
                validated, lower-cased, and trimmed before saving.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
              {columnHeaders.map((header) => (
                <div key={header}>
                  <Label htmlFor={`add-field-${header}`} className="capitalize">
                    {header}
                    {header === "email" && <span className="text-red-500 ml-1">*</span>}
                  </Label>
                  <Input
                    id={`add-field-${header}`}
                    data-testid={`list-add-field-${header}`}
                    value={addValues[header] || ""}
                    onChange={(e) => setAddValues({ ...addValues, [header]: e.target.value })}
                    className="mt-1.5"
                    type={header === "email" ? "email" : "text"}
                    placeholder={header === "email" ? "name@example.com" : ""}
                  />
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
              <Button
                onClick={handleAddRecord}
                disabled={addingRow}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="list-add-record-save-btn"
              >
                {addingRow ? "Adding…" : "Add contact"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Record Confirm */}
        <AlertDialog open={!!deleteRow} onOpenChange={(o) => !o && setDeleteRow(null)}>
          <AlertDialogContent data-testid="list-delete-row-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle>Remove this contact?</AlertDialogTitle>
              <AlertDialogDescription>
                <span className="font-mono text-slate-700">{deleteRow?.email}</span> will be
                permanently removed from this list. This cannot be undone. Other lists are not
                affected.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteRow}
                className="bg-red-600 hover:bg-red-700"
                data-testid="list-delete-row-confirm-btn"
              >
                Remove contact
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </main>
    </div>
  );
}
