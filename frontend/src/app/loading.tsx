/** Shown while a page waits for the API (S4-R11). */
export default function Loading() {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <div className="h-7 w-48 animate-pulse rounded bg-rule" />
      <div className="h-4 w-full max-w-xl animate-pulse rounded bg-rule/70" />
      <div className="h-64 w-full animate-pulse rounded-lg bg-rule/50" />
      <span className="sr-only">Loading from the FlowScore API…</span>
    </div>
  );
}
