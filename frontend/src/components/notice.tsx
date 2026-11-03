import { Info } from "lucide-react";

/**
 * The D21 notice, always on the page as text (S4-R3). Its words come from the API's `notice`
 * field, so the page and the API cannot drift apart.
 */
export function Notice({ notice }: { notice: string }) {
  return (
    <aside
      role="note"
      aria-label="About this assessment"
      className="flex items-start gap-3 rounded-lg border border-flag-rule bg-flag px-4 py-3 text-sm text-flag-ink"
    >
      <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
      <p>{notice}</p>
    </aside>
  );
}
