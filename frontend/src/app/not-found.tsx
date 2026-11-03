import Link from "next/link";

export default function NotFound() {
  return (
    <section className="max-w-2xl space-y-2 rounded-lg border border-rule bg-surface p-6">
      <h1 className="text-lg font-semibold">Not found</h1>
      <p className="text-ink-soft">There is no borrower or assessment with that id.</p>
      <Link href="/" className="inline-block font-medium text-accent underline decoration-accent/40 hover:decoration-accent">
        Back to the borrower list
      </Link>
    </section>
  );
}
