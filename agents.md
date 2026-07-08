# agents.md

This file defines the rules every agent working in this codebase must follow. Read it before writing a single line of code.

---

## 1. Goal of the Application

This is an IIoT monitoring dashboard for a manufacturing lab. It displays live telemetry from physical machines and camera feeds. The operator should be able to glance at the screen and immediately understand the state of every machine. Nothing else matters.

---

## 2. Code Style

**Write simple code.** If a junior developer cannot read a function and understand what it does in under ten seconds, rewrite it. Complexity is a bug.

**Use many small functions.** A function should do one thing. If a function is doing two things, split it. Name the function after what it does, not how it does it.

```python
# Good
def build_haas_payload(raw: dict) -> dict:
    return {
        "status": parse_haas_status(raw["status"]),
        "spindleRpm": safe_float(raw, "spindle_rpm"),
        "spindleLoad": safe_float(raw, "spindle_load"),
        "feedRate": safe_float(raw, "feed_rate"),
        "powerKw": estimate_power_kw(safe_float(raw, "spindle_load")),
        "alarms": parse_haas_alarms(raw.get("alarm", "0")),
    }

# Bad
def process(r):
    s = r.get("status", "").upper()
    if "ALARM" in s: st = "alarm"
    elif "RUNNING" in s or "CYCLE" in s: st = "running"
    else: st = "idle"
    sl = float(r.get("spindle_load", 0) or 0)
    return {"status": st, "spindleRpm": float(r.get("spindle_rpm", 0) or 0),
            "spindleLoad": sl, "powerKw": round(sl / 100.0 * 7.5, 2), ...}
```

**Favor abstraction.** If you are writing the same pattern twice, extract it into a function. If three machines share the same data shape, define one type and reuse it.

**No clever one-liners.** A readable three-line solution is always better than a clever one-liner.

---

## 3. Comments

Write comments that explain **why**, not **what**. The code explains what. If the code needs a comment to explain what it does, rewrite the code.

```python
# Good
# RTDE only allows one client at a time. Disconnect before reconnecting.
await rtde_client.disconnect()

# Bad
# ─────────────────────────────────────────────────────────────────────────────
# Disconnect the RTDE client from the robot before attempting reconnection
# ─────────────────────────────────────────────────────────────────────────────
await rtde_client.disconnect()
```

No banners. No boxes of hyphens. No section dividers made of `=` or `-` characters. A blank line between sections is sufficient.

---

## 4. Naming Conventions

Follow the conventions already established in the codebase. Do not introduce new patterns.

| Context | Convention | Example |
|---|---|---|
| Python files | `snake_case` | `haas_bridge.py` |
| Python functions | `snake_case` | `build_haas_payload()` |
| Python variables | `snake_case` | `spindle_load` |
| TypeScript files | `PascalCase` for components, `camelCase` for everything else | `MachinePanel.tsx`, `equipmentStore.ts` |
| TypeScript functions | `camelCase` | `buildHaasPayload()` |
| TypeScript types/interfaces | `PascalCase` | `HaasData`, `MachineStatus` |
| CSS variables | `--kebab-case` | `--bg-surface`, `--accent` |
| Machine identifiers | `kebab-case` strings | `"haas-tl1"`, `"ur5e"` |

If you are unsure, look at the nearest existing file and match it.

---

## 5. Only Create What Is Used

**Never create a variable, field, function, or UI element that is not actively used.**

This is the most important rule in this file.

Before adding anything, ask: is this data read somewhere? Is this function called? Is this UI element showing real, live information? If the answer is no, do not add it.

```typescript
// Good — spindleLoad is read from the WebSocket and displayed
const { spindleLoad } = useEquipmentStore(m => m.haas);
return <DataRow label="LOAD" value={spindleLoad} unit="%" />;

// Bad — field exists in the type but is never displayed or used
interface HaasData {
  spindleLoad: number;
  coolantTemp: number;    // never shown, never read, never acted on
  lastMaintenanceDate: string; // never shown, never read
}
```

```typescript
// Bad — static UI element pretending to be live data
<StatusBadge label="SYSTEM" value="ACTIVE" />
// If "ACTIVE" is hardcoded and never changes, this is decoration, not data. Remove it.
```

If a machine field is simulated and the simulation value is never used to drive any visible output or logic, do not include it in the payload.

---

## 6. UI Rules

The UI follows a strict enterprise minimalist style. The reference aesthetic is a Bloomberg Terminal or a high-end SCADA system: dense, functional, no decoration.

**Color palette — these are the only colors permitted:**

| Token | Value | Use |
|---|---|---|
| `--bg-base` | `#0D0D0D` | Page background |
| `--bg-surface` | `#141414` | Panels, sidebars |
| `--bg-elevated` | `#1C1C1C` | Hover states, selected rows |
| `--border` | `#2A2A2A` | All borders and dividers |
| `--text-primary` | `#E8E8E8` | All primary text |
| `--text-muted` | `#666666` | Labels, secondary text |
| `--accent` | `#C0441A` | Alarms, live indicators, interactive focus |

No gradients. No box shadows. No glassmorphism. No blur effects. No color outside this palette. No animations except a single opacity pulse on a live status indicator.

**Every UI element must earn its place.** Before adding a component, answer: what real information does this show the operator? If the answer is "it looks good" or "it fills the space", remove it.

**No grid items for aesthetics.** If a dashboard has four metric cards, it is because there are four metrics worth showing, not because a 2×2 grid looks balanced.

**No status badges that are always the same value.** A badge that always reads "ONLINE" or "ACTIVE" is not a status indicator. It is noise. Remove it.

**Machine panels show only:** machine name, status indicator, and the fields that are live, non-trivial, and acted upon by the operator (RPM, load, feed rate, power, active alarms). Nothing else.

---

## 7. Data Discipline

**Only store data that is displayed or used in logic.**

The backend state manager holds one snapshot per machine. Each field in that snapshot must be rendered in the UI or used in a conditional (e.g., triggering an alarm). If a field is in the snapshot but never read by the frontend, remove it from the snapshot.

The frontend store mirrors the backend snapshot. It does not add fields. It does not cache history unless a chart is actively displayed. If there is no chart, there is no history array.

```python
# Good — every field in this payload is rendered in the UI
def build_haas_payload(raw: dict) -> dict:
    return {
        "status": parse_haas_status(raw),
        "spindleRpm": safe_float(raw, "spindle_rpm"),
        "spindleLoad": safe_float(raw, "spindle_load"),
        "feedRate": safe_float(raw, "feed_rate"),
        "powerKw": estimate_power_kw(safe_float(raw, "spindle_load")),
        "alarms": parse_haas_alarms(raw.get("alarm", "0")),
    }

# Bad — fields added "just in case" or for future use
def build_haas_payload(raw: dict) -> dict:
    return {
        ...
        "coolantTemp": safe_float(raw, "coolant_temp"),   # not shown anywhere
        "cycleTimeHistory": [],                           # never populated
        "lastPollTimestamp": time.time(),                 # not shown anywhere
    }
```

---

## 8. Testing

**Test all code before it is considered done.** Write a test or a manual verification step for every bridge function, every state transformation, and every API endpoint. Do not merge code that has not been run against real or simulated inputs.

**Delete all test files after testing is complete.** Test scripts, scratch files, and temporary data files must not remain in the repository. If a test is worth keeping, it belongs in a proper `tests/` directory with a clear name. If it is a throwaway verification script, delete it.

```bash
# Good — test lives in tests/, has a clear name, is kept
tests/test_haas_payload.py

# Bad — scratch file left in repo root
test.py
scratch.py
temp_bridge_test.py
debug_output.json
```

Run the full test suite before any deployment. The test environment should mirror production as closely as possible: same Python version, same environment variables, same network assumptions.

---

## 9. Subagents and Planning

**Use subagents when work is parallelizable and homogeneous.** If you need to implement the same bridge pattern for three machines, spawn three subagents. If you need to validate five API endpoints, run them in parallel.

**Create a planning subagent before any non-trivial task.** Before writing code for a new feature, spawn a planning subagent that reads the relevant files, identifies all touch points, and produces a step-by-step plan. Only start coding after the plan is reviewed.

A planning subagent should answer:
1. What files will be created?
2. What files will be modified?
3. What tests will be written?
4. What will be deleted when done?

Do not start writing code without answers to all four questions.

---

## 10. Docker and Deployment

The entire application runs as a single Docker container. There are no separate processes to start manually. The container starts the FastAPI backend, which launches the machine bridges as asyncio tasks and the camera proxy as a subprocess.

All configuration lives in `.env`. No IP address, port, password, or API key is hardcoded in source code. If you find a hardcoded value, move it to `.env` and read it through `config.py`.

Before declaring a feature complete, verify it works inside the container, not just on the host machine.

---

## 11. What Not to Build

This list exists because these things were built in the previous version and should not be rebuilt.

- Do not build a building overview with animated floor plans unless it directly serves operator workflow.
- Do not build machine image banners or hero photos. The operator does not need to see a stock photo of a Haas lathe.
- Do not build a "wing sidebar" or zone navigation unless zones are actually selectable and show different live data.
- Do not build a global alert ticker that scrolls decorative placeholder text.
- Do not build a UR5e standalone dashboard page that duplicates data already shown on the main view.
- Do not add Radix UI components, carousels, accordions, or any interactive widget that does not serve a direct operator action.
- Do not add Framer Motion animations to data panels. Data values update instantly. Animation on data values implies the data is less current than it is.


## 12. Parting Words
If you are lost on how to build something, you can refrence ~/Documents/GE-Demo, which contains the origional code but you cannot copy it. The code there is very poorly written and cluttered, you can only ever refrence how something was done.

You are going to code in a pyramid style, where all the low-level components are built first, and then higher-level components are built on top of them. This is done so that if you ever need to stop or progress is stopped, or need to modify something, you can easily find the code you need to modify because of the human readability you delibrarately added as well as the pyramid structure.

Remember to consider UX and the rules of user waiting for a result, like a spinner or loading indicator. Consider things like this in development, the little things enterprises use to keep their user waiting so that the press of a button returning nothing doesnt mean its not working to them.