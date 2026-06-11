import { useState, useMemo } from "react";
import { Check, ChevronsUpDown, Search, Mail } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { toast } from "sonner";

// Email separator pattern — matches commas, semicolons, whitespace (including
// newlines) and any combination thereof. Used to split a pasted bulk string
// into individual addresses.
const EMAIL_SPLIT_RE = /[,;\s]+/;

/**
 * Searchable, checkbox-based multi-select for connected email accounts.
 *
 * Behaviour spec:
 * - Search filters by `email` and by `display_name`.
 * - Select-All / Clear-Selection actions in the dropdown header.
 * - Trigger shows a compact "X selected" summary.
 * - Internal scroll inside the popover (does not expand the page).
 * - Pure controlled component: parent owns `value` (array of account_ids).
 */
export default function AccountMultiSelect({
  accounts = [],
  value = [],
  onChange,
  disabled = false,
  testIdPrefix = "account-select",
  placeholder = "Select email accounts",
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return accounts;
    return accounts.filter((a) => {
      const e = (a.email || "").toLowerCase();
      const n = (a.display_name || "").toLowerCase();
      return e.includes(q) || n.includes(q);
    });
  }, [accounts, query]);

  const selectedCount = value.length;
  const allSelectedIds = accounts.map((a) => a.account_id);

  const toggle = (id) => {
    if (disabled) return;
    const next = value.includes(id) ? value.filter((x) => x !== id) : [...value, id];
    onChange(next);
  };

  const selectAll = () => onChange(allSelectedIds);
  const clearAll = () => onChange([]);

  /**
   * Bulk paste handler — accepts a string containing emails separated by
   * commas, semicolons, newlines, or whitespace. Matches each entry against
   * the connected accounts and selects every match in a single onChange call.
   *
   * If the paste yields more than one email it's treated as a bulk operation
   * and the search input is left empty (so the user immediately sees the
   * selections instead of an incomprehensible filter). For a single email
   * we fall through to the regular onChange so the input still types
   * normally.
   *
   * Returns true if a bulk-paste was handled (caller should preventDefault).
   */
  const handleBulkPaste = (text) => {
    if (!text) return false;
    const parts = text
      .split(EMAIL_SPLIT_RE)
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    if (parts.length < 2) return false; // single-email paste → normal input behaviour

    const byEmail = new Map(
      accounts.map((a) => [(a.email || "").toLowerCase(), a.account_id])
    );
    const matchedIds = new Set(value); // start from current selection
    const matchedEmails = new Set();
    const missing = [];
    const seen = new Set();
    for (const p of parts) {
      if (seen.has(p)) continue;
      seen.add(p);
      const id = byEmail.get(p);
      if (id) {
        matchedIds.add(id);
        matchedEmails.add(p);
      } else {
        missing.push(p);
      }
    }

    onChange(Array.from(matchedIds));
    setQuery("");

    const matchedCount = matchedEmails.size;
    if (matchedCount === 0) {
      toast.error(`No matching accounts — ${missing.length} email(s) not found.`);
    } else if (missing.length === 0) {
      toast.success(`${matchedCount} email account${matchedCount === 1 ? "" : "s"} selected successfully.`);
    } else {
      toast.success(
        `${matchedCount} email account${matchedCount === 1 ? "" : "s"} selected. ` +
        `${missing.length} email${missing.length === 1 ? " was" : "s were"} not found.`,
        {
          description: missing.slice(0, 5).join(", ") + (missing.length > 5 ? "…" : ""),
        }
      );
    }
    return true;
  };

  const triggerLabel =
    selectedCount === 0
      ? placeholder
      : selectedCount === 1
      ? accounts.find((a) => a.account_id === value[0])?.email || "1 account selected"
      : `${selectedCount} accounts selected`;

  return (
    <Popover open={open} onOpenChange={(o) => !disabled && setOpen(o)}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled || accounts.length === 0}
          data-testid={`${testIdPrefix}-trigger`}
          className="w-full flex items-center justify-between gap-2 border border-slate-300 rounded-md bg-white px-3 py-2 text-left text-sm hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="flex items-center gap-2 min-w-0">
            <Mail size={16} className="text-slate-400 shrink-0" />
            <span className={selectedCount === 0 ? "text-slate-500" : "text-slate-900 truncate"}>
              {triggerLabel}
            </span>
          </span>
          <ChevronsUpDown size={16} className="text-slate-400 shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="p-0 w-[var(--radix-popover-trigger-width)]"
        align="start"
        data-testid={`${testIdPrefix}-popover`}
      >
        <div className="p-2 border-b border-slate-100">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onPaste={(e) => {
                const text = e.clipboardData?.getData("text") || "";
                if (handleBulkPaste(text)) {
                  e.preventDefault();
                }
              }}
              placeholder="Search or paste emails (comma / newline / semicolon)…"
              className="pl-8 h-9 text-sm"
              data-testid={`${testIdPrefix}-search-input`}
            />
          </div>
          <div className="flex items-center justify-between mt-2 text-xs">
            <button
              type="button"
              className="text-blue-600 hover:underline disabled:text-slate-400"
              onClick={selectAll}
              disabled={accounts.length === 0 || value.length === accounts.length}
              data-testid={`${testIdPrefix}-select-all`}
            >
              Select all ({accounts.length})
            </button>
            <button
              type="button"
              className="text-slate-500 hover:text-slate-700 disabled:text-slate-300"
              onClick={clearAll}
              disabled={value.length === 0}
              data-testid={`${testIdPrefix}-clear-all`}
            >
              Clear selection
            </button>
          </div>
        </div>

        <div
          className="max-h-72 overflow-y-auto"
          data-testid={`${testIdPrefix}-list`}
        >
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-slate-500">
              {accounts.length === 0 ? "No accounts connected" : "No matches"}
            </div>
          ) : (
            filtered.map((acc) => {
              const checked = value.includes(acc.account_id);
              return (
                <label
                  key={acc.account_id}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 cursor-pointer border-b border-slate-50 last:border-0"
                  data-testid={`${testIdPrefix}-row-${acc.account_id}`}
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={() => toggle(acc.account_id)}
                    data-testid={`${testIdPrefix}-checkbox-${acc.account_id}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-900 truncate">
                      {acc.display_name || acc.email}
                    </div>
                    <div className="text-xs text-slate-500 font-mono truncate">{acc.email}</div>
                  </div>
                  {checked && <Check size={14} className="text-blue-600 shrink-0" />}
                </label>
              );
            })
          )}
        </div>

        <div className="p-2 border-t border-slate-100 flex justify-end">
          <Button size="sm" variant="outline" onClick={() => setOpen(false)}>
            Done
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
