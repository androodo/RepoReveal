import { cn } from "@/lib/utils";

export function Button({
  className,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" &&
          "bg-[var(--accent)] text-[var(--accent-fg)] hover:brightness-110",
        variant === "secondary" &&
          "border border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] hover:bg-[var(--surface-2)]",
        variant === "ghost" && "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--foreground)]",
        className,
      )}
      {...props}
    />
  );
}
