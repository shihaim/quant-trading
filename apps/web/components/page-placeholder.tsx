import Link from "next/link";

export function PagePlaceholder({
  title,
  ticketId,
  dependency,
  summary
}: {
  title: string;
  ticketId: string;
  dependency: string;
  summary: string;
}) {
  return (
    <main className="mx-auto grid w-[min(1200px,92vw)] gap-4 py-7">
      <section className="panel p-5">
        <p className="text-xs uppercase tracking-[0.08em] text-muted">{ticketId}</p>
        <h2 className="mt-1 font-display text-2xl">{title}</h2>
        <p className="mt-2 text-sm text-muted">{summary}</p>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          <div className="rounded-xl border border-black/10 p-3">
            <p className="text-xs text-muted">Status</p>
            <p className="mt-1 font-display text-base">Deferred Until V2</p>
          </div>
          <div className="rounded-xl border border-black/10 p-3">
            <p className="text-xs text-muted">Dependency</p>
            <p className="mt-1 font-display text-base">{dependency}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            href="/"
            className="rounded-md border border-black/10 bg-white px-3 py-2 text-sm transition-colors hover:bg-black/5"
          >
            Back To Home
          </Link>
        </div>
      </section>
    </main>
  );
}
