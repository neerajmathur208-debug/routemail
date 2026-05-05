import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Edit3,
  FileText,
  Image as ImageIcon,
  Save,
  Eye,
  ExternalLink,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
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
import RichTextEditor from "../components/RichTextEditor";
import { api } from "../App";
import { toast } from "sonner";

const EMPTY = {
  title: "",
  slug: "",
  excerpt: "",
  content: "",
  featured_image_url: "",
  author: "RouteMail Team",
  seo_title: "",
  seo_description: "",
  status: "draft",
};

export default function AdminBlogs({ user, setUser }) {
  const navigate = useNavigate();
  const [blogs, setBlogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // null=closed, {} for new, object for existing
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const fileInputRef = useRef(null);

  const fetchBlogs = useCallback(async () => {
    try {
      const r = await api.get("/admin/blogs");
      setBlogs(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load blogs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user && user.role !== "super_admin") {
      navigate("/dashboard", { replace: true });
      return;
    }
    fetchBlogs();
  }, [user, navigate, fetchBlogs]);

  const openNew = () => {
    setForm({ ...EMPTY });
    setEditing({});
  };
  const openEdit = (b) => {
    setForm({
      title: b.title || "",
      slug: b.slug || "",
      excerpt: b.excerpt || "",
      content: b.content || "",
      featured_image_url: b.featured_image_url || "",
      author: b.author || "RouteMail Team",
      seo_title: b.seo_title || "",
      seo_description: b.seo_description || "",
      status: b.status || "draft",
    });
    setEditing(b);
  };

  const handleUploadImage = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api.post("/admin/blogs/upload-image", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setForm((f) => ({ ...f, featured_image_url: r.data.url }));
      toast.success("Image uploaded");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSave = async () => {
    if (!form.title.trim()) { toast.error("Title is required"); return; }
    if (!form.content.trim()) { toast.error("Content is required"); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      if (!payload.slug?.trim()) delete payload.slug;
      if (editing && editing.blog_id) {
        await api.put(`/admin/blogs/${editing.blog_id}`, payload);
        toast.success("Blog updated");
      } else {
        await api.post("/admin/blogs", payload);
        toast.success("Blog created");
      }
      setEditing(null);
      fetchBlogs();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/admin/blogs/${deleteTarget.blog_id}`);
      toast.success("Blog deleted");
      setDeleteTarget(null);
      fetchBlogs();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto p-6 lg:p-10">
        <div className="flex items-center gap-3 mb-2">
          <Button variant="ghost" size="icon" onClick={() => navigate("/admin")}>
            <ArrowLeft size={20} />
          </Button>
          <h1 className="text-3xl font-bold text-slate-900 flex-1 flex items-center gap-2">
            <FileText className="text-blue-600" size={26} /> Blog management
          </h1>
          <Button
            onClick={openNew}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="admin-blog-new-btn"
          >
            <Plus size={16} className="mr-2" /> New post
          </Button>
        </div>
        <p className="text-sm text-slate-500 mb-8 ml-12">
          Public posts are visible at /blog. Drafts are hidden from public visitors.
        </p>

        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : blogs.length === 0 ? (
          <div
            className="bg-white border border-dashed border-slate-300 rounded-2xl p-16 text-center"
            data-testid="admin-blog-empty"
          >
            <FileText className="mx-auto text-slate-400 mb-3" size={40} strokeWidth={1.2} />
            <p className="text-slate-700 font-semibold">No blogs yet</p>
            <p className="text-slate-500 mt-1 mb-5">Write your first post to share with the world.</p>
            <Button onClick={openNew} className="bg-blue-600 hover:bg-blue-700 text-white">
              <Plus size={16} className="mr-2" /> New post
            </Button>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-left text-slate-500">
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Slug</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {blogs.map((b) => (
                  <tr key={b.blog_id} className="border-b border-slate-100" data-testid={`admin-blog-row-${b.slug}`}>
                    <td className="px-4 py-3 font-medium text-slate-900">{b.title}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">/{b.slug}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        b.status === "published"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}>
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {b.updated_at ? new Date(b.updated_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="inline-flex items-center gap-1">
                        {b.status === "published" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => window.open(`/blog/${b.slug}`, "_blank")}
                            title="Open public page"
                            data-testid={`admin-blog-open-${b.slug}`}
                          >
                            <ExternalLink size={14} />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(b)}
                          title="Edit"
                          data-testid={`admin-blog-edit-${b.slug}`}
                        >
                          <Edit3 size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteTarget(b)}
                          title="Delete"
                          className="text-red-500 hover:text-red-600 hover:bg-red-50"
                          data-testid={`admin-blog-delete-${b.slug}`}
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Editor dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto" data-testid="admin-blog-editor">
          <DialogHeader>
            <DialogTitle>{editing?.blog_id ? "Edit blog post" : "New blog post"}</DialogTitle>
            <DialogDescription>
              Drafts are hidden from the public site. Publish to make it visible at /blog/{form.slug || "<slug>"}.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Title *</Label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="How we 10x'd cold-email reply rates"
                  data-testid="admin-blog-title"
                />
              </div>
              <div>
                <Label>Slug</Label>
                <Input
                  value={form.slug}
                  onChange={(e) => setForm({ ...form, slug: e.target.value })}
                  placeholder="auto-generated from title if empty"
                  data-testid="admin-blog-slug"
                />
              </div>
            </div>

            <div>
              <Label>Excerpt</Label>
              <Textarea
                rows={2}
                value={form.excerpt}
                onChange={(e) => setForm({ ...form, excerpt: e.target.value })}
                placeholder="Short teaser shown on /blog list"
                data-testid="admin-blog-excerpt"
              />
            </div>

            <div>
              <Label>Featured image</Label>
              <div className="flex items-center gap-3 mt-1.5">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleUploadImage}
                  className="hidden"
                  data-testid="admin-blog-image-input"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  data-testid="admin-blog-upload-image-btn"
                >
                  <ImageIcon size={14} className="mr-2" />
                  {uploading ? "Uploading…" : form.featured_image_url ? "Replace image" : "Upload image"}
                </Button>
                {form.featured_image_url && (
                  <>
                    <img src={form.featured_image_url} alt="" className="h-12 w-20 object-cover rounded-md" />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setForm({ ...form, featured_image_url: "" })}
                      className="text-red-500"
                    >
                      Remove
                    </Button>
                  </>
                )}
              </div>
              <Input
                className="mt-2 text-xs"
                value={form.featured_image_url}
                onChange={(e) => setForm({ ...form, featured_image_url: e.target.value })}
                placeholder="…or paste an image URL"
              />
            </div>

            <div>
              <Label>Content *</Label>
              <RichTextEditor
                value={form.content}
                onChange={(v) => setForm({ ...form, content: v })}
                placeholder="Write your post here…"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Author</Label>
                <Input
                  value={form.author}
                  onChange={(e) => setForm({ ...form, author: e.target.value })}
                  data-testid="admin-blog-author"
                />
              </div>
              <div>
                <Label>Status</Label>
                <Select
                  value={form.status}
                  onValueChange={(v) => setForm({ ...form, status: v })}
                >
                  <SelectTrigger data-testid="admin-blog-status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="published">Published</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="border-t border-slate-200 pt-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">SEO</p>
              <div>
                <Label>Meta title</Label>
                <Input
                  value={form.seo_title}
                  onChange={(e) => setForm({ ...form, seo_title: e.target.value })}
                  placeholder="Defaults to post title if empty"
                />
              </div>
              <div>
                <Label>Meta description</Label>
                <Textarea
                  rows={2}
                  value={form.seo_description}
                  onChange={(e) => setForm({ ...form, seo_description: e.target.value })}
                  placeholder="~155 char summary for search engines"
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
            <Button
              onClick={handleSave}
              disabled={saving}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="admin-blog-save-btn"
            >
              <Save size={14} className="mr-2" />
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent data-testid="admin-blog-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this post?</AlertDialogTitle>
            <AlertDialogDescription>
              "{deleteTarget?.title}" will be permanently removed. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
              data-testid="admin-blog-delete-confirm-btn"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
