import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import axios from "axios";
import { Button } from "../components/ui/button";
import { ArrowLeft, Calendar, User as UserIcon } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL + "/api";

export default function BlogList() {
  const navigate = useNavigate();
  const [blogs, setBlogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = "Blog — RouteMail";
    axios
      .get(`${API}/blogs/public`)
      .then((r) => setBlogs(r.data || []))
      .catch(() => setBlogs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-white border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 h-20 flex items-center justify-between">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900"
            data-testid="blog-back-home-btn"
          >
            <ArrowLeft size={16} /> Home
          </button>
          <img
            src="/routemail-logo.png"
            alt="RouteMail"
            className="h-12 w-auto"
          />
          <Button onClick={() => navigate("/login")} variant="ghost" data-testid="blog-nav-login-btn">
            Sign In
          </Button>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-16">
        <header className="mb-12 text-center">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900">
            The RouteMail Blog
          </h1>
          <p className="mt-3 text-lg text-slate-600">
            Cold-email playbooks, deliverability tips, and product updates.
          </p>
        </header>

        {loading ? (
          <div className="text-center text-slate-500">Loading…</div>
        ) : blogs.length === 0 ? (
          <div
            className="text-center text-slate-500 bg-white border border-dashed border-slate-300 rounded-2xl py-16"
            data-testid="blog-empty-state"
          >
            No posts yet. Check back soon.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {blogs.map((b, idx) => (
              <motion.article
                key={b.blog_id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(idx, 6) * 0.05 }}
                onClick={() => navigate(`/blog/${b.slug}`)}
                className="cursor-pointer bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-md transition-shadow"
                data-testid={`blog-card-${b.slug}`}
              >
                {b.featured_image_url ? (
                  <img
                    src={b.featured_image_url}
                    alt={b.title}
                    className="w-full h-44 object-cover"
                  />
                ) : (
                  <div className="w-full h-44 bg-gradient-to-br from-slate-100 to-slate-200" />
                )}
                <div className="p-5">
                  <h2 className="font-bold text-slate-900 text-lg leading-snug">
                    {b.title}
                  </h2>
                  {b.excerpt && (
                    <p className="mt-2 text-sm text-slate-600 line-clamp-3">{b.excerpt}</p>
                  )}
                  <div className="mt-4 flex items-center gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1.5">
                      <UserIcon size={12} /> {b.author || "RouteMail Team"}
                    </span>
                    {b.published_at && (
                      <span className="flex items-center gap-1.5">
                        <Calendar size={12} />
                        {new Date(b.published_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    )}
                  </div>
                </div>
              </motion.article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
