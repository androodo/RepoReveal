"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  getSystemTheme,
  type Theme,
} from "@/lib/theme";

type ThemeContextValue = {
  theme: Theme;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: Theme) => void;
  ready: boolean;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

type Listener = () => void;
const listeners = new Set<Listener>();
let clientTheme: Theme | null = null;

function emit() {
  listeners.forEach((listener) => listener());
}

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // ignore
  }
  return "system";
}

function getClientTheme(): Theme {
  if (clientTheme === null) {
    clientTheme = readStoredTheme();
  }
  return clientTheme;
}

function setClientTheme(theme: Theme) {
  clientTheme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore
  }
  applyTheme(theme);
  emit();
}

function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function useIsClient() {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const isClient = useIsClient();
  const theme = useSyncExternalStore<Theme>(subscribe, getClientTheme, () => "system");

  useEffect(() => {
    if (!isClient) return;
    applyTheme(theme);
  }, [theme, isClient]);

  useEffect(() => {
    if (!isClient || theme !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme, isClient]);

  const setTheme = useCallback((next: Theme) => {
    setClientTheme(next);
  }, []);

  const resolvedTheme = useMemo(() => {
    if (!isClient) return "light" as const;
    return theme === "system" ? getSystemTheme() : theme;
  }, [theme, isClient]);

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
      ready: isClient,
    }),
    [theme, resolvedTheme, setTheme, isClient],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return ctx;
}
