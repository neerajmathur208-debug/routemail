import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  FileText,
  Users,
  Trash2,
  Eye,
  Plus,
  Edit2,
  Calendar,
  Tag,
  ArrowLeft,
  Check,
  X,
  AlertCircle,
  Download,
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../components/ui/tooltip";
import Sidebar from "../components/Sidebar";
import { api, API } from "../App";
import { toast } from "sonner";

export default function EmailLists({ user, setUser }) {
  const navigate = useNavigate();
  const [lists, setLists] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedList, setSelectedList] = useState(null);
  const [editingListId, setEditingListId] = useState(null);
  const [editName, setEditName] = useState("");

  const fetchData = async () => {
    try {
      const [listsRes, campaignsRes] = await Promise.all([
        api.get("/lists"),
        api.get("/campaigns"),
      ]);
      setLists(listsRes.data);
      setCampaigns(campaignsRes.data);
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error("Failed to load email lists");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getListStatus = (listId) => {
    const usedInCampaign = campaigns.some(c => c.list_id === listId);
    return usedInCampaign ? "used" : "active";
  };

  const handleStartRename = (list) => {
    setEditingListId(list.list_id);
    setEditName(list.name);
  };

  const handleCancelRename = () => {
    setEditingListId(null);
    setEditName("");
  };

  const handleSaveRename = async (listId) => {
    if (!editName.trim()) {
      toast.error("List name cannot be empty");
      return;
    }

    try {
      await api.put(`/lists/${listId}`, { name: editName.trim() });
      toast.success("List renamed successfully");
      setEditingListId(null);
      setEditName("");
      fetchData();
    } catch (error) {
      toast.error("Failed to rename list");
    }
  };

  const handleDeleteClick = (list) => {
    setSelectedList(list);
    setDeleteDialogOpen(true);
  };

  const handleDeleteList = async () => {
    if (!selectedList) return;

    try {
      await api.delete(`/lists/${selectedList.list_id}`);
      toast.success("List deleted successfully");
      setDeleteDialogOpen(false);
      setSelectedList(null);
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to delete list";
      toast.error(message);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
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

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-8">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/dashboard")}
              data-testid="back-btn"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex-1">
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                Email Lists
              </h1>
              <p className="text-slate-500 mt-1">
                Manage your uploaded email contact lists
              </p>
            </div>
            <Button
              onClick={() => navigate("/upload")}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="upload-new-list-btn"
            >
              <Plus size={18} className="mr-2" />
              Upload New List
            </Button>
          </div>

          {/* Lists Table/Cards */}
          {lists.length > 0 ? (
            <div className="bg-white border border-slate-200 rounded-md overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>List Name</TableHead>
                    <TableHead className="text-center">Total Contacts</TableHead>
                    <TableHead>Date Uploaded</TableHead>
                    <TableHead>Column Headers</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lists.map((list, index) => {
                    const status = getListStatus(list.list_id);
                    const isEditing = editingListId === list.list_id;

                    return (
                      <motion.tr
                        key={list.list_id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.03 }}
                        className="border-b border-slate-100 hover:bg-slate-50"
                      >
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-slate-100 rounded-md flex items-center justify-center flex-shrink-0">
                              <FileText size={18} className="text-slate-500" />
                            </div>
                            {isEditing ? (
                              <div className="flex items-center gap-2">
                                <Input
                                  value={editName}
                                  onChange={(e) => setEditName(e.target.value)}
                                  className="h-8 w-48"
                                  autoFocus
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") handleSaveRename(list.list_id);
                                    if (e.key === "Escape") handleCancelRename();
                                  }}
                                  data-testid={`edit-name-input-${list.list_id}`}
                                />
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-8 w-8"
                                  onClick={() => handleSaveRename(list.list_id)}
                                  data-testid={`save-name-${list.list_id}`}
                                >
                                  <Check size={16} className="text-green-600" />
                                </Button>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-8 w-8"
                                  onClick={handleCancelRename}
                                  data-testid={`cancel-name-${list.list_id}`}
                                >
                                  <X size={16} className="text-slate-400" />
                                </Button>
                              </div>
                            ) : (
                              <div>
                                <p className="font-medium text-slate-900">{list.name}</p>
                                {list.original_filename && list.original_filename !== list.name && (
                                  <p className="text-xs text-slate-400">{list.original_filename}</p>
                                )}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-1">
                            <Users size={14} className="text-slate-400" />
                            <span className="font-medium">{list.valid_emails || 0}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1 text-sm text-slate-500">
                            <Calendar size={14} />
                            {formatDate(list.created_at)}
                          </div>
                        </TableCell>
                        <TableCell>
                          {list.column_headers && list.column_headers.length > 0 ? (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div className="flex items-center gap-1 cursor-help">
                                    <Tag size={14} className="text-slate-400" />
                                    <span className="text-sm text-slate-500">
                                      {list.column_headers.length} fields
                                    </span>
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent side="top" className="max-w-xs">
                                  <div className="flex flex-wrap gap-1">
                                    {list.column_headers.map((h) => (
                                      <Badge key={h} variant="secondary" className="text-xs">
                                        {`{{${h}}}`}
                                      </Badge>
                                    ))}
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          ) : (
                            <span className="text-sm text-slate-400">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {status === "used" ? (
                            <Badge variant="secondary" className="bg-blue-100 text-blue-700">
                              Used in Campaign
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="bg-green-100 text-green-700">
                              Active
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => navigate(`/email-lists/${list.list_id}`)}
                              data-testid={`view-list-${list.list_id}`}
                            >
                              <Eye size={16} className="text-slate-400" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => window.open(`${API}/lists/${list.list_id}/export`, "_blank")}
                              data-testid={`download-list-${list.list_id}`}
                              title="Download CSV"
                            >
                              <Download size={16} className="text-slate-400 hover:text-blue-600" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleStartRename(list)}
                              disabled={isEditing}
                              data-testid={`rename-list-${list.list_id}`}
                            >
                              <Edit2 size={16} className="text-slate-400" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteClick(list)}
                              data-testid={`delete-list-${list.list_id}`}
                            >
                              <Trash2 size={16} className="text-slate-400 hover:text-red-500" />
                            </Button>
                          </div>
                        </TableCell>
                      </motion.tr>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-md p-12 text-center">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Users size={32} className="text-slate-400" />
              </div>
              <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
                No email lists yet
              </h3>
              <p className="text-slate-500 mb-6">
                Upload your first CSV file to create an email list
              </p>
              <Button
                onClick={() => navigate("/upload")}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="upload-first-list-btn"
              >
                <Plus size={18} className="mr-2" />
                Upload Email List
              </Button>
            </div>
          )}

          {/* Info Box */}
          <div className="mt-6 p-4 bg-slate-100 rounded-md">
            <h3 className="font-semibold text-slate-900 mb-2 flex items-center gap-2">
              <AlertCircle size={16} />
              About Email Lists
            </h3>
            <ul className="text-sm text-slate-600 space-y-1">
              <li>• Each uploaded CSV creates a new independent list</li>
              <li>• Lists used in active campaigns cannot be deleted</li>
              <li>• Column headers become personalization variables like {"{{first_name}}"}</li>
              <li>• You can upload as many lists as you need</li>
            </ul>
          </div>
        </div>
      </main>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">
              Delete Email List
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedList?.name}"? This will permanently
              remove all {selectedList?.valid_emails || 0} contacts. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-btn">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteList}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-delete-btn"
            >
              Delete List
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
