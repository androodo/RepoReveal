export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <div className="h-8 w-64 animate-pulse rounded bg-[var(--surface-2)]" />
      <div className="mt-4 h-4 w-96 animate-pulse rounded bg-[var(--surface-2)]" />
    </div>
  );
}
