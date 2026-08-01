export type Theme = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "reporeveal-theme";

export function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function resolveTheme(theme: Theme): "light" | "dark" {
  return theme === "system" ? getSystemTheme() : theme;
}

export function applyTheme(theme: Theme): void {
  const resolved = resolveTheme(theme);
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;
}

/** Inline script for the document head — prevents theme flash before hydration. */
export const themeInitScript = `(() => {
  try {
    const key = ${JSON.stringify(THEME_STORAGE_KEY)};
    const stored = localStorage.getItem(key);
    const theme = stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const resolved = theme === "system" ? (prefersDark ? "dark" : "light") : theme;
    const root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.style.colorScheme = resolved;
  } catch (_) {}
})();`;
