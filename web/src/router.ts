import { useCallback, useEffect, useState } from "react";

export function useRouter() {
  const [path, setPath] = useState(() => window.location.pathname);
  const [search, setSearch] = useState(() => window.location.search);

  useEffect(() => {
    const onPopState = () => {
      setPath(window.location.pathname);
      setSearch(window.location.search);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((next: string, replace = false) => {
    const url = new URL(next, window.location.origin);
    window.history[replace ? "replaceState" : "pushState"]({}, "", url);
    setPath(url.pathname);
    setSearch(url.search);
    if (!window.navigator.userAgent.includes("jsdom")) {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, []);

  return { path, search, navigate };
}
