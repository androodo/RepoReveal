"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/providers/theme-provider";

export function ThemeToggle() {
  const { resolvedTheme, setTheme, ready } = useTheme();
  const dark = resolvedTheme === "dark";

  return (
    <Button
      type="button"
      variant="ghost"
      aria-label="Toggle theme"
      disabled={!ready}
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="h-9 w-9 p-0"
    >
      {/* Stable placeholder until client theme is known — avoids hydration mismatch */}
      {!ready ? (
        <span className="h-4 w-4" aria-hidden />
      ) : dark ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  );
}
