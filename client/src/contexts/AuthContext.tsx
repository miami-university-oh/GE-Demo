import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface AuthState {
  authenticated: boolean;
  username: string;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => boolean;
  logout: () => void;
}

const DEMO_CREDENTIALS: Record<string, string> = {
  admin: "GEdemo2026",
  demo: "IIoT@McNair",
};

const SESSION_KEY = "iiot-auth";

/**
 * Reads and validates auth state from `sessionStorage`.
 *
 * @returns The stored {@link AuthState} if it contains a valid authenticated session,
 *   or `{ authenticated: false, username: '' }` on parse error or missing/invalid data.
 */
function loadSession(): AuthState {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed.authenticated && parsed.username) return parsed;
    }
  } catch {}
  return { authenticated: false, username: "" };
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Provides auth context to the subtree.
 *
 * Reads the persisted session from `sessionStorage` on mount and exposes `login` and
 * `logout` via context. Session state is written back to `sessionStorage` on login and
 * cleared on logout.
 *
 * @param children - React subtree that requires auth context.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(loadSession);

  /**
   * Validates credentials against `DEMO_CREDENTIALS`. On success, persists the session
   * to `sessionStorage` and updates auth state.
   *
   * @param username - Case-insensitive username.
   * @param password - Plaintext password.
   * @returns `true` on successful authentication, `false` otherwise.
   */
  const login = useCallback((username: string, password: string): boolean => {
    const expected = DEMO_CREDENTIALS[username.toLowerCase()];
    if (expected && expected === password) {
      const next: AuthState = { authenticated: true, username };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
      setState(next);
      return true;
    }
    return false;
  }, []);

  /**
   * Removes the session from `sessionStorage` and resets auth state to unauthenticated.
   */
  const logout = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    setState({ authenticated: false, username: "" });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Returns the current {@link AuthContextValue} (auth state + login/logout functions).
 *
 * @throws If called outside of an {@link AuthProvider}.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
