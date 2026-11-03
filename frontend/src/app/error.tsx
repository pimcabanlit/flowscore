"use client";

import { Button } from "@/components/ui/button";

/** Anything the pages did not expect (S4-R11). Shows no stack trace. */
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section role="alert" className="max-w-2xl space-y-3 rounded-lg border border-rule bg-surface p-6">
      <h1 className="text-lg font-semibold">Something went wrong on this page</h1>
      <p className="text-ink-soft">Check that the FlowScore API is running, then try again.</p>
      <Button variant="quiet" onClick={reset}>
        Try again
      </Button>
    </section>
  );
}
