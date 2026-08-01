"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  return (
    <Button
      type="button"
      variant="ghost"
      aria-label="Toggle theme"
      suppressHydrationWarning
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="h-9 w-9 p-0"
    >
      <span suppressHydrationWarning>
        {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </span>
    </Button>
  );
}
