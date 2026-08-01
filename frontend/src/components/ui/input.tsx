import { cn } from "@/lib/utils";

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--foreground)] outline-none ring-[var(--accent)] placeholder:text-[var(--muted)] focus:ring-2",
        className,
      )}
      {...props}
    />
  );
}
