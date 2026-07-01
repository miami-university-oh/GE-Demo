import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import { ArrowLeft, ExternalLink, RefreshCw, Radio, CircleOff } from "lucide-react";

const DASHBOARD_URL = "http://localhost:8080";
const POLL_INTERVAL = 3000;

export default function UR5eDashboard() {
  const [, navigate] = useLocation();
  const [status, setStatus] = useState<"checking" | "online" | "offline">("checking");

  const checkServer = useCallback(() => {
    setStatus("checking");
    const img = new Image();
    img.onload = () => setStatus("online");
    img.onerror = () => {
      fetch(DASHBOARD_URL, { mode: "no-cors" })
        .then(() => setStatus("online"))
        .catch(() => setStatus("offline"));
    };
    img.src = `${DASHBOARD_URL}/favicon.ico?_=${Date.now()}`;
  }, []);

  useEffect(() => {
    checkServer();
    const id = setInterval(checkServer, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [checkServer]);

  return (
    <div className="fixed inset-0 flex flex-col bg-background">
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-4 py-2 flex-shrink-0"
        style={{
          background: "oklch(0.09 0.025 240)",
          borderBottom: "1px solid oklch(1 0 0 / 8%)",
        }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors hover:bg-[oklch(1_0_0/8%)]"
            style={{ color: "oklch(0.55 0.015 230)" }}
          >
            <ArrowLeft size={14} />
            Building Dashboard
          </button>

          <div
            className="h-5 w-px"
            style={{ background: "oklch(1 0 0 / 10%)" }}
          />

          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded flex items-center justify-center"
              style={{
                background: "oklch(0.65 0.18 280 / 20%)",
                border: "1px solid oklch(0.65 0.18 280 / 40%)",
              }}
            >
              <span className="text-xs">🤖</span>
            </div>
            <div>
              <div className="text-sm font-semibold text-white leading-tight">
                UR5e RTDE Dashboard
              </div>
              <div
                className="text-[9px] tracking-widest uppercase"
                style={{ color: "oklch(0.50 0.015 230)" }}
              >
                Telemetry · Control · Digital Twin
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Status badge */}
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-semibold tracking-wider uppercase font-data"
            style={{
              background:
                status === "online"
                  ? "oklch(0.65 0.18 155 / 12%)"
                  : status === "checking"
                    ? "oklch(0.72 0.18 85 / 12%)"
                    : "oklch(0.45 0.01 240 / 15%)",
              color:
                status === "online"
                  ? "oklch(0.65 0.18 155)"
                  : status === "checking"
                    ? "oklch(0.72 0.18 85)"
                    : "oklch(0.50 0.015 230)",
              border: `1px solid ${
                status === "online"
                  ? "oklch(0.65 0.18 155 / 30%)"
                  : status === "checking"
                    ? "oklch(0.72 0.18 85 / 30%)"
                    : "oklch(0.45 0.01 240 / 20%)"
              }`,
            }}
          >
            {status === "online" ? (
              <Radio size={10} className="pulse-live" />
            ) : (
              <CircleOff size={10} />
            )}
            {status === "online"
              ? "Connected"
              : status === "checking"
                ? "Checking…"
                : "Server Offline"}
          </div>

          <button
            onClick={checkServer}
            className="p-1.5 rounded transition-colors hover:bg-[oklch(1_0_0/8%)]"
            style={{ color: "oklch(0.50 0.015 230)" }}
            title="Refresh connection"
          >
            <RefreshCw size={14} />
          </button>

          <a
            href={DASHBOARD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded transition-colors hover:bg-[oklch(1_0_0/8%)]"
            style={{ color: "oklch(0.50 0.015 230)" }}
            title="Open in new tab"
          >
            <ExternalLink size={14} />
          </a>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 relative">
        {status === "online" ? (
          <iframe
            src={DASHBOARD_URL}
            className="w-full h-full border-0"
            title="UR5e RTDE Dashboard"
            allow="fullscreen"
          />
        ) : (
          <div className="flex items-center justify-center h-full dot-grid-bg">
            <div
              className="pointer-events-none absolute"
              style={{
                width: 500,
                height: 500,
                borderRadius: "50%",
                background:
                  "radial-gradient(circle, oklch(0.65 0.18 280 / 6%) 0%, transparent 70%)",
                top: "50%",
                left: "50%",
                transform: "translate(-50%, -50%)",
              }}
            />

            <div
              className="relative z-10 max-w-lg mx-4 rounded-xl border panel-glow p-8 text-center"
              style={{ background: "oklch(0.11 0.025 240)" }}
            >
              <div
                className="w-16 h-16 mx-auto mb-4 rounded-xl flex items-center justify-center"
                style={{
                  background: "oklch(0.65 0.18 280 / 15%)",
                  border: "1px solid oklch(0.65 0.18 280 / 30%)",
                }}
              >
                <span className="text-3xl">🤖</span>
              </div>

              <h2 className="text-xl font-semibold text-white mb-2">
                UR5e Dashboard Server
              </h2>
              <p
                className="text-sm mb-6"
                style={{ color: "oklch(0.55 0.015 230)" }}
              >
                The UR5e NiceGUI dashboard is not running. Start the Python
                server to connect.
              </p>

              <div
                className="rounded-lg p-4 mb-6 text-left"
                style={{
                  background: "oklch(0.08 0.02 240)",
                  border: "1px solid oklch(1 0 0 / 8%)",
                }}
              >
                <div
                  className="text-[10px] tracking-widest uppercase font-semibold mb-2"
                  style={{ color: "oklch(0.45 0.015 230)" }}
                >
                  Start Command
                </div>
                <code
                  className="font-data text-sm block"
                  style={{ color: "oklch(0.65 0.18 155)" }}
                >
                  python machine-bridges/ur5e_dashboard.py
                </code>
                <div
                  className="text-xs mt-3"
                  style={{ color: "oklch(0.45 0.015 230)" }}
                >
                  Dependencies:{" "}
                  <code style={{ color: "oklch(0.55 0.015 230)" }}>
                    pip install nicegui plotly
                  </code>
                </div>
                <div
                  className="text-xs mt-1"
                  style={{ color: "oklch(0.45 0.015 230)" }}
                >
                  Optional:{" "}
                  <code style={{ color: "oklch(0.55 0.015 230)" }}>
                    pip install ur-rtde pyrealsense2 opencv-python
                  </code>
                </div>
              </div>

              <div
                className="flex items-center justify-center gap-2 text-xs"
                style={{ color: "oklch(0.40 0.015 230)" }}
              >
                <RefreshCw size={12} className={status === "checking" ? "animate-spin" : ""} />
                Auto-checking every {POLL_INTERVAL / 1000}s…
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
