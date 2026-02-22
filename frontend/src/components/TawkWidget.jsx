import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export default function TawkWidget() {
  const location = useLocation();
  
  // Pages where Tawk should appear
  const allowedPaths = ["/dashboard", "/campaign", "/admin", "/accounts", "/email-lists", "/upload"];
  const shouldShow = allowedPaths.some(path => location.pathname.startsWith(path));

  useEffect(() => {
    // Only load on authenticated pages
    if (!shouldShow) {
      // Remove widget if navigating away
      if (window.Tawk_API?.hideWidget) {
        window.Tawk_API.hideWidget();
      }
      return;
    }

    // Check if script is already loaded
    if (window.Tawk_API) {
      if (window.Tawk_API.showWidget) {
        window.Tawk_API.showWidget();
      }
      return;
    }

    // Initialize Tawk.to
    window.Tawk_API = window.Tawk_API || {};
    window.Tawk_LoadStart = new Date();

    const script = document.createElement("script");
    script.async = true;
    script.src = "https://embed.tawk.to/699b33ddfdade21c3afe3047/1ji3456kt";
    script.charset = "UTF-8";
    script.setAttribute("crossorigin", "*");

    const firstScript = document.getElementsByTagName("script")[0];
    if (firstScript && firstScript.parentNode) {
      firstScript.parentNode.insertBefore(script, firstScript);
    } else {
      document.body.appendChild(script);
    }

    return () => {
      // Hide widget when component unmounts
      if (window.Tawk_API?.hideWidget) {
        window.Tawk_API.hideWidget();
      }
    };
  }, [shouldShow, location.pathname]);

  return null;
}
