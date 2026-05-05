import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { ArrowLeft, Calendar, User as UserIcon } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function BlogDetail() {
  const navigate = useNavigate();
  const { slug } = useParams();
  const [blog, setBlog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    axios
      .get(`${API}/blogs/public/${slug}`)
      .then((r) => {
        const b = r.data;
        setBlog(b);
        document.title = (b.seo_title || b.title) + " — RouteMail";
        // Update meta description
        let meta = document.querySelector('meta[name="description"]');
        if (!meta) {
          meta = document.createElement("meta");
          meta.setAttribute("name", "description");
          document.head.appendChild(meta);
        }
        meta.setAttribute("content", b.seo_description || b.excerpt || "");
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [slug]);

  return (
    <div className="min-h-screen bg-white">
      <nav className="bg-white border-b border-slate-100 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
          <button
            onClick={() => navigate("/blog")}
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 text-sm"
            data-testid="blog-detail-back-btn"
          >
            <ArrowLeft size={16} /> All posts
          </button>
          <Button onClick={() => navigate("/")} variant="ghost" size="sm">
            Home
          </Button>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-12">
        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : notFound || !blog ? (
          <div
            className="text-center bg-slate-50 border border-dashed border-slate-300 rounded-2xl py-16 text-slate-600"
            data-testid="blog-not-found"
          >
            <p className="text-lg font-semibold">Post not found</p>
            <p className="text-sm mt-2">It may have been moved or unpublished.</p>
            <Button
              className="mt-4"
              variant="outline"
              onClick={() => navigate("/blog")}
            >
              Back to blog
            </Button>
          </div>
        ) : (
          <article data-testid={`blog-article-${blog.slug}`}>
            <h1 className="text-4xl font-extrabold text-slate-900 leading-tight">
              {blog.title}
            </h1>
            <div className="mt-4 flex items-center gap-5 text-sm text-slate-500 border-b border-slate-200 pb-6">
              <span className="flex items-center gap-1.5">
                <UserIcon size={14} /> {blog.author || "RouteMail Team"}
              </span>
              {blog.published_at && (
                <span className="flex items-center gap-1.5">
                  <Calendar size={14} />
                  {new Date(blog.published_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </span>
              )}
            </div>
            {blog.featured_image_url && (
              <img
                src={blog.featured_image_url}
                alt={blog.title}
                className="w-full mt-8 rounded-xl object-cover max-h-[420px]"
              />
            )}
            <div
              className="prose prose-lg max-w-none mt-8 text-slate-800"
              dangerouslySetInnerHTML={{ __html: blog.content }}
            />
          </article>
        )}
      </main>
    </div>
  );
}
