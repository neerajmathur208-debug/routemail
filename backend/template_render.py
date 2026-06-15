"""Robust template rendering for outbound emails.

Fixes the long-standing bug where unresolved variables (``{{name}}``, ``{}``,
``{{}}``) and stray HTML entities (``&nbsp;``) were being delivered to
recipients verbatim.

Public API:
    render_template(template, data, fallbacks=None) -> str
    extract_template_variables(template) -> set[str]
    analyse_contacts(template, contacts, optional_fields=None) -> dict
    clean_html_artifacts(text) -> str
"""
from __future__ import annotations

import html
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# Match {{ first_name }} / {{First Name}} / {{first.name}} — letters, digits,
# spaces, underscores, dots and hyphens between the braces.
_DOUBLE_BRACE_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.\- ]+?)\s*\}\}")

# Match {first_name} (single brace) for legacy drip templates.
_SINGLE_BRACE_RE = re.compile(r"(?<!\{)\{\s*([A-Za-z0-9_.\- ]+?)\s*\}(?!\})")

# Empty / partial braces left over after rendering.
_EMPTY_BRACES_RE = re.compile(r"\{\{\s*\}\}|\{\s*\}")

# Stray un-rendered double-brace tokens (should never reach the recipient).
_STRAY_DOUBLE_BRACE_RE = re.compile(r"\{\{[^{}]*\}\}")

# Generic per-variable fallback when neither the contact row nor the campaign
# config supplies a value.
_GENERIC_FALLBACKS = {
    "first_name": "there",
    "firstname": "there",
    "name": "there",
}


def _normalise_key(k: str) -> str:
    """Lower-case + collapse whitespace + replace dot/dash with underscore."""
    return re.sub(r"[\s\.\-]+", "_", k.strip().lower())


def _lookup(data: Dict[str, Any], var_name: str) -> Optional[str]:
    """Look up a variable case-insensitively, returning ``None`` when missing
    OR empty (so callers can apply fallbacks)."""
    if not data:
        return None
    target = _normalise_key(var_name)
    for raw_key, raw_val in data.items():
        if _normalise_key(str(raw_key)) == target:
            if raw_val is None:
                return None
            s = str(raw_val).strip()
            return s or None
    return None


def render_template(
    template: Optional[str],
    data: Optional[Dict[str, Any]] = None,
    fallbacks: Optional[Dict[str, str]] = None,
) -> str:
    """Render a template string against ``data``.

    Resolution order for ``{{var}}``:
        1. exact case-insensitive match in ``data``
        2. ``fallbacks[var]`` if provided (campaign-level)
        3. generic fallback (``"there"`` for first_name-style tokens)
        4. empty string (so the variable disappears entirely — never leaked)

    Strips stray ``{}``, ``{{}}``, and any un-rendered ``{{tokens}}`` left
    behind. Also runs :func:`clean_html_artifacts` once at the end so callers
    never need to repeat that step.
    """
    if not template:
        return ""
    data = data or {}
    fallbacks = fallbacks or {}

    # 1. Double-brace pass
    def _double(match: "re.Match[str]") -> str:
        var = match.group(1)
        val = _lookup(data, var)
        if val is not None:
            return val
        fb = fallbacks.get(_normalise_key(var))
        if fb:
            return str(fb)
        return _GENERIC_FALLBACKS.get(_normalise_key(var), "")
    rendered = _DOUBLE_BRACE_RE.sub(_double, template)

    # 2. Single-brace pass (legacy drip templates) — only replace when the
    # data actually has the key, otherwise leave the literal text alone
    # (could be JSON braces in unrelated content).
    def _single(match: "re.Match[str]") -> str:
        var = match.group(1)
        val = _lookup(data, var)
        if val is not None:
            return val
        # Strip single-brace placeholders only if they look like template tokens
        # (no spaces or punctuation outside the allowed set already matched).
        return ""
    rendered = _SINGLE_BRACE_RE.sub(_single, rendered)

    # 3. Hard-strip leftover empty braces + un-rendered double-brace tokens
    rendered = _EMPTY_BRACES_RE.sub("", rendered)
    rendered = _STRAY_DOUBLE_BRACE_RE.sub("", rendered)

    return clean_html_artifacts(rendered)


def clean_html_artifacts(text: str) -> str:
    """Replace orphan HTML entities and obvious cruft from rich-text editors.

    * Convert literal ``&nbsp;`` to a regular space (NBSP is allowed inside
      HTML, but here we collapse it so plain-text views are clean).
    * Decode any remaining HTML entities once (``&amp;`` → ``&``).
    * Collapse 3+ consecutive blank lines.
    """
    if not text:
        return ""

    # Common stray entities — replace BEFORE html.unescape() so the result of
    # double-encoded HTML stays sane.
    out = text.replace("&nbsp;", " ").replace("&NBSP;", " ")

    # Single pass of html.unescape() converts the remaining named/numeric
    # entities. Doing it once (not in a loop) avoids accidentally decoding
    # user-typed `&amp;amp;`.
    try:
        out = html.unescape(out)
    except Exception:
        pass

    # Collapse run-on blank lines (>2 → 2) to clean up imported drafts.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


# ---------------------------------------------------------------------------
# Pre-send analysis (used by /campaigns/{id}/preflight)
# ---------------------------------------------------------------------------


def extract_template_variables(template: Optional[str]) -> Set[str]:
    """Return the set of variable names referenced by ``template`` (normalised)."""
    if not template:
        return set()
    names: Set[str] = set()
    for m in _DOUBLE_BRACE_RE.finditer(template):
        names.add(_normalise_key(m.group(1)))
    for m in _SINGLE_BRACE_RE.finditer(template):
        names.add(_normalise_key(m.group(1)))
    return names


def analyse_contacts(
    template_parts: Iterable[str],
    contacts: Iterable[Dict[str, Any]],
    optional_fields: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Pre-flight check for a campaign / drip body+subject.

    Args:
        template_parts: every template string to scan (subject, body, body_text,
            and each drip step subject/body).
        contacts: iterable of contact dicts that will actually be merged in.
        optional_fields: variable names that should NOT count as broken when
            missing (e.g. ``unsubscribe_url``).

    Returns dict shaped as:
        ``{variables: [str], total_contacts, missing_per_variable: {var: int},
        unresolved_samples: [{email, missing: [str]}], warnings: [str]}``.
    """
    optional_fields = {_normalise_key(x) for x in (optional_fields or {"unsubscribe_url"})}
    variables: Set[str] = set()
    for part in template_parts:
        variables |= extract_template_variables(part)

    variables -= optional_fields

    contact_list: List[Dict[str, Any]] = list(contacts or [])
    total = len(contact_list)

    missing_per_variable: Dict[str, int] = {v: 0 for v in variables}
    unresolved_samples: List[Dict[str, Any]] = []

    for c in contact_list:
        merged = {**(c.get("data") or {}), **{k: v for k, v in c.items() if k not in ("data", "_id")}}
        missing_here: List[str] = []
        for v in variables:
            if _lookup(merged, v) is None:
                missing_per_variable[v] += 1
                missing_here.append(v)
        if missing_here and len(unresolved_samples) < 10:
            unresolved_samples.append({
                "email": c.get("email") or c.get("contact_email") or "",
                "missing": missing_here,
            })

    warnings: List[str] = []
    if total == 0:
        warnings.append("No recipients to validate — add contacts first.")
    if variables and total > 0:
        per_var = [
            f"{v} (missing in {missing_per_variable[v]}/{total})"
            for v in variables
            if missing_per_variable[v] > 0
        ]
        if per_var:
            warnings.append("Some recipients are missing required variables: " + ", ".join(per_var))

    return {
        "variables": sorted(variables),
        "total_contacts": total,
        "missing_per_variable": missing_per_variable,
        "unresolved_samples": unresolved_samples,
        "warnings": warnings,
        "ok": not warnings,
    }


# ---------------------------------------------------------------------------
# Drop-in shim — kept for callers still importing ``replace_variables``.
# ---------------------------------------------------------------------------


def replace_variables(template: Optional[str], data: Optional[Dict[str, Any]] = None) -> str:
    """Backwards-compatible name for :func:`render_template`."""
    return render_template(template, data)
