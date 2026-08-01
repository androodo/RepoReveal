import { RepositoryForm } from "@/components/repository/repository-form";

export default function HomePage() {
  return (
    <div>
      <section className="hero-atmosphere flex min-h-[calc(100svh-3.5rem)] flex-col justify-center px-4 py-10 sm:py-16">
        <div className="mx-auto w-full max-w-4xl">
          <p className="mb-4 text-sm font-medium uppercase tracking-[0.16em] text-[var(--accent)] sm:text-base">
            RepoReveal
          </p>
          <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-[var(--foreground)] sm:text-5xl lg:text-6xl lg:leading-[1.08]">
            Reveal how any codebase works.
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--muted)] sm:text-lg sm:leading-8">
            Paste a public Python repository to explore its architecture, dependencies, entry
            points and important files—and ask questions grounded in the actual code.
          </p>
          <div className="mt-8 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm sm:p-5">
            <RepositoryForm />
          </div>
        </div>
      </section>

      <section className="landing-features border-t border-[var(--border)] px-4 py-12 sm:py-16">
        <div className="mx-auto grid max-w-6xl gap-10 md:grid-cols-3 md:gap-8">
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
              <h2 className="text-base font-semibold text-[var(--foreground)] sm:text-lg">
                {item.title}
              </h2>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)] sm:text-[15px] sm:leading-7">
                {item.body}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
