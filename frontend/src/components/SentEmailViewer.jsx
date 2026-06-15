import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "./ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Button } from "./ui/button";
import { Loader2, Mail, Code, ExternalLink, Copy, AlertCircle } from "lucide-react";
import { api } from "../App";
import { toast } from "sonner";

/**
 * SentEmailViewer
 * - `sentId` (preferred)  OR  `lookup={recipient_email, campaign_id?, drip_id?}` to find the most recent send
 * - Renders Preview + HTML Source tabs of the *delivered* email.
 */
export default function SentEmailViewer({ open, onClose, sentId, lookup }) {
  const [loading, setLoading] = useState(false);
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) {
      setDoc(null);
      setError(null);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        let res;
        if (sentId) {
          res = await api.get(`/sent-emails/${sentId}`);
        } else if (lookup?.recipient_email) {
          const params = new URLSearchParams({ recipient_email: lookup.recipient_email });
          if (lookup.campaign_id) params.set("campaign_id", lookup.campaign_id);
          if (lookup.drip_id) params.set("drip_id", lookup.drip_id);
          res = await api.get(`/sent-emails/by-recipient?${params.toString()}`);
        } else {
          throw new Error("Either sentId or lookup is required");
        }
        if (!cancelled) setDoc(res.data);
      } catch (e) {
        if (!cancelled) {
          if (e?.response?.status === 404) {
            setError(
              "No stored copy of this email yet. The Sent Email Viewer only captures emails sent after the Phase-2 update — historical sends won't be available."
            );
          } else {
            setError(e?.response?.data?.detail || e.message || "Failed to load");
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [open, sentId, lookup?.recipient_email, lookup?.campaign_id, lookup?.drip_id]);

  const copyHtml = () => {
    if (!doc?.body_html) return;
    navigator.clipboard.writeText(doc.body_html).then(
      () => toast.success("HTML copied to clipboard"),
      () => toast.error("Copy failed")
    );
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="sm:max-w-[820px] max-h-[90vh] overflow-hidden flex flex-col" data-testid="sent-email-viewer">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail size={18} className="text-violet-600" /> Sent Email
            {doc?.drip_step_number ? (
              <span className="text-xs font-normal text-slate-500">
                · drip step {doc.drip_step_number}
              </span>
            ) : null}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="py-10 text-center text-sm text-slate-500" data-testid="sent-email-loading">
            <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
          </div>
        ) : error ? (
          <div className="py-6 border border-amber-200 bg-amber-50 rounded-lg p-4 text-sm text-amber-800" data-testid="sent-email-error">
            <AlertCircle className="inline-block mr-2" size={14} />
            {error}
          </div>
        ) : doc ? (
          <div className="space-y-3 overflow-hidden flex flex-col">
            {/* Header grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1 text-sm" data-testid="sent-email-meta">
              <MetaRow label="To" value={doc.recipient_email} />
              <MetaRow
                label="From"
                value={
                  doc.from_name && doc.sender_email
                    ? `${doc.from_name} <${doc.sender_email}>`
                    : doc.from_name || doc.sender_email || "—"
                }
              />
              <MetaRow label="Subject" value={doc.subject} bold />
              <MetaRow
                label="Sent"
                value={doc.sent_at ? new Date(doc.sent_at).toLocaleString() : "—"}
              />
              {doc.campaign_name && <MetaRow label="Campaign" value={doc.campaign_name} />}
              {doc.drip_campaign_name && (
                <MetaRow
                  label="Drip"
                  value={`${doc.drip_campaign_name} (step ${doc.drip_step_number || "?"})`}
                />
              )}
            </div>

            <Tabs defaultValue="preview" className="flex-1 overflow-hidden flex flex-col">
              <TabsList className="mb-2 w-fit">
                <TabsTrigger value="preview" data-testid="sent-email-tab-preview">
                  <Mail size={13} className="mr-1.5" /> Preview
                </TabsTrigger>
                <TabsTrigger value="html" data-testid="sent-email-tab-html">
                  <Code size={13} className="mr-1.5" /> HTML Source
                </TabsTrigger>
                {doc.body_text && (
                  <TabsTrigger value="text" data-testid="sent-email-tab-text">
                    Plain Text
                  </TabsTrigger>
                )}
              </TabsList>

              <TabsContent value="preview" className="flex-1 overflow-auto border border-slate-200 rounded-md bg-white p-4" data-testid="sent-email-preview">
                {doc.body_html ? (
                  // sandboxed iframe so internal CSS doesn't pollute the app
                  <iframe
                    title="Sent email preview"
                    srcDoc={doc.body_html}
                    sandbox=""
                    className="w-full min-h-[400px] border-0"
                    data-testid="sent-email-iframe"
                  />
                ) : (
                  <div className="text-sm text-slate-500">
                    No HTML body stored for this email.
                  </div>
                )}
              </TabsContent>

              <TabsContent value="html" className="flex-1 overflow-auto border border-slate-200 rounded-md bg-slate-50" data-testid="sent-email-html-source">
                <div className="flex items-center justify-between px-3 py-1.5 border-b border-slate-200 sticky top-0 bg-slate-50">
                  <span className="text-xs uppercase tracking-wider text-slate-500">
                    HTML source
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={copyHtml}
                    data-testid="sent-email-copy-html"
                  >
                    <Copy size={12} className="mr-1.5" /> Copy
                  </Button>
                </div>
                <pre className="p-3 text-xs whitespace-pre-wrap break-all text-slate-800 font-mono">
                  {doc.body_html || "(empty)"}
                </pre>
              </TabsContent>

              {doc.body_text && (
                <TabsContent value="text" className="flex-1 overflow-auto border border-slate-200 rounded-md bg-white" data-testid="sent-email-plain-text">
                  <pre className="p-3 text-sm whitespace-pre-wrap text-slate-800">
                    {doc.body_text}
                  </pre>
                </TabsContent>
              )}
            </Tabs>
          </div>
        ) : null}

        <DialogFooter>
          {doc?.message_id && (
            <a
              href={`mailto:${doc.recipient_email}?subject=${encodeURIComponent("Re: " + (doc.subject || ""))}`}
              className="text-xs text-slate-500 hover:text-slate-800 inline-flex items-center gap-1 mr-auto"
            >
              <ExternalLink size={12} /> Open in mail client
            </a>
          )}
          <Button variant="outline" onClick={onClose} data-testid="sent-email-close">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MetaRow({ label, value, bold }) {
  return (
    <div className="flex gap-2">
      <span className="text-[11px] uppercase tracking-wider text-slate-500 w-16 flex-shrink-0">
        {label}
      </span>
      <span className={`text-sm break-all ${bold ? "font-semibold text-slate-900" : "text-slate-700"}`}>
        {value || "—"}
      </span>
    </div>
  );
}
