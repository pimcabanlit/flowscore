"use client";

import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Stores a new assessment as of the borrower's history_end, which the API supplied (S4-R9).
 * Goes through the /api/v1 rewrite to POST /api/v1/borrowers/{id}/assessments.
 */
export function RunAssessmentButton({ borrowerId, asOf, label }: { borrowerId: string; asOf: string; label: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/borrowers/${encodeURIComponent(borrowerId)}/assessments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ as_of: asOf }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const detail = Array.isArray(body?.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : null;
        throw new Error(detail ?? `The API answered ${res.status}.`);
      }
      const made = (await res.json()) as { id: number };
      router.push(`/assessments/${made.id}`);
    } catch (e) {
      setError(e instanceof Error && e.message !== "Failed to fetch" ? e.message : "The API is not answering.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <Button onClick={run} disabled={busy} aria-busy={busy}>
        {busy ? <LoaderCircle aria-hidden className="size-4 animate-spin" /> : null}
        {busy ? "Assessing…" : label}
      </Button>
      {error ? (
        <p role="alert" className="text-sm text-out">
          Could not run the assessment: {error}
        </p>
      ) : null}
    </div>
  );
}
