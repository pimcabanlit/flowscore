import { CircleAlert } from "lucide-react";

import type { ApiProblem as Problem } from "@/lib/api";
import { ApiError } from "@/lib/api";

const TEXT: Record<Problem, { title: string; fix: React.ReactNode }> = {
  unreachable: {
    title: "The FlowScore API is not answering",
    fix: (
      <>
        Start it from the repository root with <code>uvicorn backend.app.main:app --reload</code>, or set{" "}
        <code>FLOWSCORE_API_URL</code> to where it runs, then reload this page.
      </>
    ),
  },
  "no-database": {
    title: "The API has no database",
    fix: (
      <>
        Set <code>FLOWSCORE_DATABASE_URL</code> before starting the API, run <code>alembic upgrade head</code> and{" "}
        <code>python scripts\seed_demo_database.py</code>, then reload this page.
      </>
    ),
  },
  "not-found": { title: "Not found", fix: "Go back to the borrower list and choose again." },
  failed: {
    title: "The API returned an error",
    fix: "Check the API's console for the request, then reload this page.",
  },
};

/** A page-level explanation of an API failure, with the way out (S4-R11). Never a stack trace. */
export function ApiProblemPanel({ error }: { error: unknown }) {
  const problem: Problem = error instanceof ApiError ? error.problem : "failed";
  const status = error instanceof ApiError ? error.status : undefined;
  const t = TEXT[problem];
  return (
    <section role="alert" className="max-w-2xl rounded-lg border border-rule bg-surface p-6">
      <h1 className="flex items-center gap-2 text-lg font-semibold">
        <CircleAlert aria-hidden className="size-5 text-out" />
        {t.title}
        {status ? <span className="text-sm font-normal text-ink-faint">(HTTP {status})</span> : null}
      </h1>
      <p className="mt-2 text-ink-soft [&_code]:rounded [&_code]:bg-paper [&_code]:px-1 [&_code]:text-[0.9em]">
        {t.fix}
      </p>
    </section>
  );
}

/** Run an API call; a 404 is returned as null so the page can call notFound(). */
export async function load<T>(call: () => Promise<T>): Promise<{ ok: true; data: T } | { ok: false; error: unknown }> {
  try {
    return { ok: true, data: await call() };
  } catch (error) {
    return { ok: false, error };
  }
}
