import { RepositoryForm } from "@/components/repository/repository-form";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-20 pt-16">
      <section className="max-w-3xl">
        <p className="mb-3 text-sm font-medium uppercase tracking-[0.14em] text-[var(--accent)]">
          RepoReveal
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-[var(--foreground)] sm:text-5xl">
          Reveal how any codebase works.
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-[var(--muted)]">
          Paste a public Python repository to explore its architecture, dependencies, entry
          points and important files—and ask questions grounded in the actual code.
        </p>
        <div className="mt-8 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm">
          <RepositoryForm />
        </div>
      </section>

      <section className="mt-16 grid gap-8 border-t border-[var(--border)] pt-12 md:grid-cols-3">
        {[
          {
            title: "Static analysis first",
            body: "RepoReveal parses Python with AST, builds an import graph, and ranks files without executing anything.",
          },
          {
            title: "Interactive architecture",
            body: "Inspect entry points, dependency edges, and structural change impact across the repository.",
          },
          {
            title: "Grounded answers",
            body: "AI explanations use retrieved evidence and validated citations—never the whole repository at once.",
          },
        ].map((item) => (
          <div key={item.title}>
            <h2 className="text-base font-semibold text-[var(--foreground)]">{item.title}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{item.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
