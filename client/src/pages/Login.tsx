import { useState, type FormEvent } from "react";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Full-screen login page for the IIoT Building Dashboard.
 * Submits credentials to `useAuth().login` with a 400 ms artificial delay
 * to show a loading state. Displays an inline error message on invalid
 * credentials. On success, `AuthGate` re-renders and redirects the user
 * to the app without an explicit navigation call.
 */
export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    setTimeout(() => {
      const ok = login(username.trim(), password);
      if (!ok) setError("Invalid credentials");
      setLoading(false);
    }, 400);
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-background dot-grid-bg">
      {/* Ambient glow */}
      <div
        className="pointer-events-none absolute"
        style={{
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, oklch(0.65 0.18 220 / 8%) 0%, transparent 70%)",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
      />

      <form
        onSubmit={handleSubmit}
        className="relative z-10 w-full max-w-md mx-4 rounded-xl border panel-glow p-8"
        style={{ background: "oklch(0.11 0.025 240)" }}
      >
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 mb-3 px-3 py-1 rounded-full text-xs font-medium tracking-widest uppercase"
               style={{ background: "oklch(0.65 0.18 155 / 12%)", color: "oklch(0.65 0.18 155)" }}>
            <span className="inline-block w-1.5 h-1.5 rounded-full pulse-live" style={{ background: "oklch(0.65 0.18 155)" }} />
            Secure Access
          </div>
          <h1 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            IIoT Building Dashboard
          </h1>
          <p className="mt-1 text-sm" style={{ color: "oklch(0.55 0.015 230)" }}>
            Advanced Manufacturing Hub — Miami University
          </p>
        </div>

        {/* Username */}
        <div className="mb-4">
          <label className="block text-xs font-medium tracking-wider uppercase mb-1.5"
                 style={{ color: "oklch(0.55 0.015 230)" }}>
            Username
          </label>
          <input
            type="text"
            autoComplete="username"
            autoFocus
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm font-data bg-transparent outline-none transition-colors
                       focus:border-[oklch(0.65_0.18_220)] focus:ring-1 focus:ring-[oklch(0.65_0.18_220/40%)]"
            style={{ borderColor: "oklch(1 0 0 / 10%)" }}
            placeholder="admin"
          />
        </div>

        {/* Password */}
        <div className="mb-6">
          <label className="block text-xs font-medium tracking-wider uppercase mb-1.5"
                 style={{ color: "oklch(0.55 0.015 230)" }}>
            Password
          </label>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border px-3 py-2.5 text-sm font-data bg-transparent outline-none transition-colors
                       focus:border-[oklch(0.65_0.18_220)] focus:ring-1 focus:ring-[oklch(0.65_0.18_220/40%)]"
            style={{ borderColor: "oklch(1 0 0 / 10%)" }}
            placeholder="••••••••"
          />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 rounded-lg px-3 py-2 text-sm"
               style={{ background: "oklch(0.62 0.22 25 / 12%)", color: "oklch(0.75 0.18 25)" }}>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg py-2.5 text-sm font-semibold tracking-wide uppercase transition-all disabled:opacity-50"
          style={{
            background: "oklch(0.65 0.18 220)",
            color: "oklch(0.08 0.02 240)",
          }}
        >
          {loading ? "Authenticating…" : "Access Dashboard"}
        </button>

        {/* Footer */}
        <p className="mt-6 text-center text-xs" style={{ color: "oklch(0.40 0.01 240)" }}>
          Miami University — Powered by BWC
        </p>
      </form>
    </div>
  );
}
