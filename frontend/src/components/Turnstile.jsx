import { useEffect, useRef } from "react";

/**
 * Cloudflare Turnstile widget.
 *
 * Loads the official `challenges.cloudflare.com/turnstile/v0/api.js` script
 * (singleton — only inserted once per page lifecycle) and renders a Turnstile
 * widget into a div ref. The widget's solved token is delivered to `onToken`.
 *
 * Reset behaviour: when the parent calls `reset()` via the optional `widgetRef`
 * prop, the widget regenerates its token (used after a failed login/register).
 */
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=__routemailTurnstileOnLoad__&render=explicit";

function loadTurnstileScript() {
  return new Promise((resolve, reject) => {
    if (window.turnstile) return resolve();
    // If script is already in the DOM, just wait for it to finish loading.
    const existing = document.querySelector(`script[src^="https://challenges.cloudflare.com/turnstile/v0/api.js"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }
    // Global callback Cloudflare's script will fire when the API is ready
    window.__routemailTurnstileOnLoad__ = () => resolve();
    const s = document.createElement("script");
    s.src = SCRIPT_SRC;
    s.async = true;
    s.defer = true;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

export default function Turnstile({ siteKey, onToken, onExpire, onError, theme = "auto", widgetRef }) {
  const containerRef = useRef(null);
  const widgetIdRef = useRef(null);

  useEffect(() => {
    if (!siteKey) {
      // No site key configured — silently degrade. Backend will treat as dev-mode.
      return;
    }
    let cancelled = false;
    let localWidgetId = null;
    loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return;
        localWidgetId = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          theme,
          callback: (token) => onToken?.(token),
          "expired-callback": () => {
            onExpire?.();
            onToken?.("");
          },
          "error-callback": () => {
            onError?.();
            onToken?.("");
          },
        });
        widgetIdRef.current = localWidgetId;
        if (widgetRef) {
          widgetRef.current = {
            reset: () => {
              if (widgetIdRef.current && window.turnstile) {
                window.turnstile.reset(widgetIdRef.current);
              }
            },
          };
        }
      })
      .catch(() => {
        onError?.();
      });

    return () => {
      cancelled = true;
      try {
        if (widgetIdRef.current && window.turnstile?.remove) {
          window.turnstile.remove(widgetIdRef.current);
        }
      } catch (e) { /* ignore */ }
      widgetIdRef.current = null;
    };
    // We deliberately don't depend on the callback props — they may be inline lambdas.
  }, [siteKey, theme]);

  return (
    <div className="flex justify-center w-full" data-testid="turnstile-container">
      <div ref={containerRef} className="cf-turnstile" />
    </div>
  );
}
