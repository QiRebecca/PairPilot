const RECOVERY_KEY = "pairpilot:chunk-recovery-at";
const RECOVERY_WINDOW_MS = 60_000;

export function installChunkRecovery(
  reload: () => void = () => window.location.reload(),
  now: () => number = () => Date.now(),
): () => void {
  const onPreloadError = (event: Event) => {
    const lastRecovery = Number(sessionStorage.getItem(RECOVERY_KEY) || "0");
    const timestamp = now();
    if (timestamp - lastRecovery < RECOVERY_WINDOW_MS) return;
    event.preventDefault();
    sessionStorage.setItem(RECOVERY_KEY, String(timestamp));
    reload();
  };
  window.addEventListener("vite:preloadError", onPreloadError);
  return () => window.removeEventListener("vite:preloadError", onPreloadError);
}
