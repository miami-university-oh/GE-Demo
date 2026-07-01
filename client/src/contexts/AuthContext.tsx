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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(loadSession);

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

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
