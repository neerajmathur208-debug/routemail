import { useEffect, useRef } from "react";

/**
 * useAutoSaveDraft — Runs `save()` when the user navigates away or closes the tab.
 *
 *   const save = useCallback(async () => { ... }, [deps]);
 *   useAutoSaveDraft(save, dirtyFlag);
 *
 * - Fires on component unmount (covers route changes + browser back).
 * - Fires on `beforeunload` (covers tab close / hard refresh, best-effort).
 * - Skips entirely when `dirty` is falsy so we don't spam the API.
 */
export default function useAutoSaveDraft(save, dirty) {
  // Keep a fresh reference to `save` so cleanup uses the latest closure
  const saveRef = useRef(save);
  const dirtyRef = useRef(dirty);
  useEffect(() => {
    saveRef.current = save;
    dirtyRef.current = dirty;
  }, [save, dirty]);

  useEffect(() => {
    const handler = (e) => {
      if (dirtyRef.current && typeof saveRef.current === "function") {
        // Don't await — browsers ignore async work in beforeunload, but the call
        // will still dispatch best-effort.
        try {
          saveRef.current();
        } catch (_) {
          /* ignore */
        }
        // Modern browsers ignore returnValue text but still trigger confirm.
        e.preventDefault();
        e.returnValue = "";
        return "";
      }
      return undefined;
    };
    window.addEventListener("beforeunload", handler);
    return () => {
      window.removeEventListener("beforeunload", handler);
      // Component unmount — covers SPA route changes + back navigation
      if (dirtyRef.current && typeof saveRef.current === "function") {
        try {
          saveRef.current();
        } catch (_) {
          /* ignore */
        }
      }
    };
    // Intentionally empty deps — handler reads from refs, so it always sees latest
  }, []);
}
