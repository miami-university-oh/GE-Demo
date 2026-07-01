import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme?: () => void;
  switchable: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
  switchable?: boolean;
}

/**
 * Applies the active theme class to `document.documentElement` and provides theme
 * context to the subtree.
 *
 * When `switchable` is `true`, the selected theme is persisted to `localStorage` and
 * a `toggleTheme` function is exposed via context. When `switchable` is `false` (default),
 * the theme is locked to `defaultTheme` and `toggleTheme` is `undefined`.
 *
 * @param children - React subtree that consumes theme context.
 * @param defaultTheme - Initial theme to apply. Defaults to `'light'`.
 * @param switchable - Whether the user can toggle between themes. Defaults to `false`.
 */
export function ThemeProvider({
  children,
  defaultTheme = "light",
  switchable = false,
}: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (switchable) {
      const stored = localStorage.getItem("theme");
      return (stored as Theme) || defaultTheme;
    }
    return defaultTheme;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }

    if (switchable) {
      localStorage.setItem("theme", theme);
    }
  }, [theme, switchable]);

  const toggleTheme = switchable
    ? () => {
        setTheme(prev => (prev === "light" ? "dark" : "light"));
      }
    : undefined;

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, switchable }}>
      {children}
    </ThemeContext.Provider>
  );
}

/**
 * Returns the current theme context: `{ theme, toggleTheme, switchable }`.
 *
 * `toggleTheme` is `undefined` when the provider was created with `switchable={false}`.
 *
 * @throws If called outside of a {@link ThemeProvider}.
 */
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
