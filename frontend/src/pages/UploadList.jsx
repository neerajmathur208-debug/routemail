import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Eye,
  Users,
  Tag,
  ArrowLeft,
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
import { api } from "../App";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

export default function UploadList({ user, setUser }) {
  const navigate = useNavigate();
  const [lists, setLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [listName, setListName] = useState("");
  const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedList, setSelectedList] = useState(null);
  const [viewListData, setViewListData] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const fetchLists = async () => {
    try {
      const response = await api.get("/lists");
      setLists(response.data);
    } catch (error) {
      console.error("Failed to fetch lists:", error);
      toast.error("Failed to load lists");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLists();
  }, []);

  const handleFileUpload = async (file) => {
    if (!file) return;

    if (!file.name.endsWith(".csv")) {
      toast.error("Please upload a CSV file");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await api.post("/lists/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setPreviewData(response.data);
      setListName(file.name.replace(".csv", ""));
      setPreviewDialogOpen(true);
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to process CSV";
      toast.error(message);
    } finally {
      setUploading(false);
    }
  };

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  }, []);

  const handleSaveList = async () => {
    if (!listName.trim()) {
      toast.error("Please enter a list name");
      return;
    }

    setSaving(true);
    try {
      await api.post("/lists", {
        name: listName,
        original_filename: previewData.original_filename,
        column_headers: previewData.column_headers,
        emails: previewData.emails,
      });
      toast.success("Email list saved successfully");
      setPreviewDialogOpen(false);
      setPreviewData(null);
      setListName("");
      fetchLists();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to save list";
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleViewList = async (list) => {
    try {
      const response = await api.get(`/lists/${list.list_id}`);
      setViewListData(response.data);
      setViewDialogOpen(true);
    } catch (error) {
      toast.error("Failed to load list details");
    }
  };

  const handleDeleteList = async () => {
    if (!selectedList) return;

    try {
      await api.delete(`/lists/${selectedList.list_id}`);
      toast.success("List deleted successfully");
      setDeleteDialogOpen(false);
      setSelectedList(null);
      fetchLists();
    } catch (error) {
      toast.error("Failed to delete list");
    }
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

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          {/* Header with Back Button */}
          <div className="flex items-center gap-4 mb-8">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/dashboard")}
              data-testid="back-btn"
            >
              <ArrowLeft size={20} />
            </Button>
            <div>
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                Upload List
              </h1>
              <p className="text-slate-500 mt-1">
                Upload and manage your email contact lists
              </p>
            </div>
          </div>

          {/* Upload Zone */}
          <div
            className={`
              border-2 border-dashed rounded-lg p-8 text-center transition-colors
              ${dragActive ? "border-electric-blue bg-blue-50" : "border-slate-300 bg-white"}
            `}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Upload size={32} className="text-slate-400" />
            </div>
            <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
              Drop your CSV file here
            </h3>
            <p className="text-slate-500 mb-4">or click to browse</p>
            <input
              type="file"
              accept=".csv"
              className="hidden"
              id="csv-upload"
              onChange={(e) => handleFileUpload(e.target.files?.[0])}
              disabled={uploading}
            />
            <label htmlFor="csv-upload">
              <Button
                variant="outline"
                className="cursor-pointer"
                disabled={uploading}
                asChild
              >
                <span data-testid="select-file-btn">
                  {uploading ? "Processing..." : "Select File"}
                </span>
              </Button>
            </label>
            <p className="text-xs text-slate-400 mt-4">
              CSV must include an "email" column. Additional columns become personalization variables.
            </p>
          </div>

          {/* Existing Lists */}
          <div className="mt-8">
            <h2 className="font-heading font-semibold text-lg text-slate-900 mb-4">
              Your Lists
            </h2>

            {lists.length > 0 ? (
              <div className="space-y-3">
                {lists.map((list, index) => (
                  <motion.div
                    key={list.list_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="bg-white border border-slate-200 rounded-md p-4"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-slate-100 rounded-md flex items-center justify-center">
                          <FileText size={20} className="text-slate-500" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900">{list.name}</p>
                          <p className="text-sm text-slate-500">
                            {list.valid_emails} contacts
                            {list.total_rows !== list.valid_emails && (
                              <span className="text-slate-400">
                                {" "}
                                ({list.total_rows - list.valid_emails} suppressed)
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleViewList(list)}
                          data-testid={`view-list-${list.list_id}`}
                        >
                          <Eye size={18} className="text-slate-400" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setSelectedList(list);
                            setDeleteDialogOpen(true);
                          }}
                          data-testid={`delete-list-${list.list_id}`}
                        >
                          <Trash2 size={18} className="text-slate-400 hover:text-red-500" />
                        </Button>
                      </div>
                    </div>
                    
                    {/* Column Headers / Variables */}
                    {list.column_headers && list.column_headers.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-100">
                        <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                          <Tag size={12} />
                          Available Variables:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {list.column_headers.map((header) => (
                            <Badge
                              key={header}
                              variant="secondary"
                              className="text-xs"
                            >
                              {`{{${header}}}`}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="bg-white border border-slate-200 rounded-md p-8 text-center">
                <Users size={32} className="mx-auto mb-3 text-slate-300" />
                <p className="text-slate-500">No lists uploaded yet</p>
              </div>
            )}
          </div>

          {/* CSV Format Guide */}
          <div className="mt-8 p-4 bg-slate-100 rounded-md">
            <h3 className="font-semibold text-slate-900 mb-2">CSV Format Guide</h3>
            <p className="text-sm text-slate-600 mb-3">
              Your CSV file should have these columns (additional columns become variables):
            </p>
            <div className="bg-white rounded border border-slate-200 p-3 font-mono text-sm overflow-x-auto">
              <p className="text-slate-500">email,first_name,company,city,custom_field</p>
              <p>john@example.com,John,Acme Inc,New York,Premium</p>
              <p>jane@example.com,Jane,Tech Corp,Boston,Standard</p>
            </div>
            <p className="text-xs text-slate-500 mt-3">
              Each column becomes a variable like {"{{first_name}}"}, {"{{company}}"}, etc.
            </p>
          </div>
        </div>
      </main>

      {/* Preview Dialog */}
      <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading font-semibold">
              Preview & Save List
            </DialogTitle>
            <DialogDescription>
              Review your uploaded contacts and available variables
            </DialogDescription>
          </DialogHeader>

          {previewData && (
            <div className="py-4 space-y-4">
              <div>
                <Label htmlFor="list-name">List Name</Label>
                <Input
                  id="list-name"
                  value={listName}
                  onChange={(e) => setListName(e.target.value)}
                  placeholder="My Email List"
                  className="mt-1.5"
                  data-testid="list-name-input"
                />
              </div>

              <div className="flex items-center gap-6 p-4 bg-slate-50 rounded-md">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={18} className="text-green-600" />
                  <span className="text-sm text-slate-700">
                    <strong>{previewData.valid_emails}</strong> valid emails
                  </span>
                </div>
                {previewData.total_rows > previewData.valid_emails && (
                  <div className="flex items-center gap-2">
                    <AlertCircle size={18} className="text-amber-500" />
                    <span className="text-sm text-slate-700">
                      <strong>{previewData.total_rows - previewData.valid_emails}</strong> invalid/duplicates removed
                    </span>
                  </div>
                )}
              </div>

              {/* Available Variables */}
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm font-medium text-blue-800 mb-2 flex items-center gap-2">
                  <Tag size={16} />
                  Available Variables for Personalization:
                </p>
                <div className="flex flex-wrap gap-2">
                  {previewData.column_headers.map((header) => (
                    <Badge
                      key={header}
                      className="bg-blue-100 text-blue-700 hover:bg-blue-200"
                    >
                      {`{{${header}}}`}
                    </Badge>
                  ))}
                </div>
                <p className="text-xs text-blue-600 mt-2">
                  Use these variables in your email subject and body
                </p>
              </div>

              <div className="csv-preview">
                <p className="text-sm font-medium text-slate-700 mb-2">Preview (first 10):</p>
                <div className="border rounded-md overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {previewData.column_headers.map((header) => (
                          <TableHead key={header} className="whitespace-nowrap">
                            {header}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewData.preview.map((row, i) => (
                        <TableRow key={i}>
                          {previewData.column_headers.map((header) => (
                            <TableCell key={header} className="font-mono text-sm whitespace-nowrap">
                              {row[header] || "-"}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setPreviewDialogOpen(false);
                setPreviewData(null);
              }}
              data-testid="cancel-save-btn"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveList}
              disabled={saving}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="save-list-btn"
            >
              {saving ? "Saving..." : "Save List"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View List Dialog */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="sm:max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading font-semibold">
              {viewListData?.name}
            </DialogTitle>
            <DialogDescription>
              {viewListData?.valid_emails} contacts
            </DialogDescription>
          </DialogHeader>

          {viewListData && (
            <div className="py-4 space-y-4">
              {/* Variables */}
              {viewListData.column_headers && viewListData.column_headers.length > 0 && (
                <div className="p-3 bg-slate-50 rounded-md">
                  <p className="text-xs text-slate-500 mb-2">Available Variables:</p>
                  <div className="flex flex-wrap gap-1">
                    {viewListData.column_headers.map((header) => (
                      <Badge key={header} variant="secondary" className="text-xs">
                        {`{{${header}}}`}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              <div className="csv-preview">
                <div className="border rounded-md overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {(viewListData.column_headers || ["email"]).map((header) => (
                          <TableHead key={header} className="whitespace-nowrap">
                            {header}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {viewListData.emails.slice(0, 50).map((row, i) => (
                        <TableRow key={i}>
                          {(viewListData.column_headers || ["email"]).map((header) => (
                            <TableCell key={header} className="font-mono text-sm whitespace-nowrap">
                              {row[header] || "-"}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                {viewListData.emails.length > 50 && (
                  <p className="text-sm text-slate-500 mt-3 text-center">
                    Showing first 50 of {viewListData.emails.length} contacts
                  </p>
                )}
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setViewDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">
              Delete List
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedList?.name}"? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-list-btn">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteList}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-delete-list-btn"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
