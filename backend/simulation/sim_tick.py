import asyncio
import logging
import random

from backend.config import settings

logger = logging.getLogger(__name__)

# Persist simulation state between ticks for smooth drift
sim_state = {
    "makino_a51nx": {
        "rpm": 8000.0,
        "load": 60.0,
        "feed": 3000.0,
        "part_count": 0,
        "tick_count": 0,
        "status": "idle"
    },
    "makino_d200z": {
        "rpm": 12000.0,
        "load": 45.0,
        "feed": 2000.0,
        "part_count": 0,
        "tick_count": 0,
        "status": "idle"
    },
    "makino_ps95": {
        "rpm": 10000.0,
        "load": 55.0,
        "feed": 5000.0,
        "part_count": 0,
        "tick_count": 0,
        "status": "idle"
    },
    "haas": {
        "rpm": 1800.0,
        "load": 35.0,
        "feed": 200.0,
        "part_count": 0,
        "tick_count": 0,
        "status": "idle"
    },
    "ur5e": {
        "angles": [0.0] * 6,
        "tcp": [300.0, -100.0, 200.0, 0.0, 0.0, 0.0],
    }
}

PROGRAMS = ["O0001", "O0002", "O0003"]

def drift(value: float, delta: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value + (random.random() - 0.5) * 2 * delta))


def update_makino_sim(machine_id: str, base_rpm: float, max_rpm: float, max_power: float, max_tools: int):
    st = sim_state[machine_id]
    st["tick_count"] += 1

    # Randomly change status
    r = random.random()
    if r < 0.05:
        st["status"] = "alarm"
    elif r < 0.20:
        st["status"] = "idle"
    else:
        st["status"] = "running"

    if st["status"] == "running":
        st["rpm"] = drift(st["rpm"], max_rpm * 0.02, base_rpm * 0.8, max_rpm)
        st["load"] = drift(st["load"], 3.0, 10.0, 100.0)
        st["feed"] = drift(st["feed"], base_rpm * 0.01, 0, base_rpm)
        if st["tick_count"] % 20 == 0:
            st["part_count"] += 1
    else:
        st["rpm"] = 0.0
        st["load"] = 0.0
        st["feed"] = 0.0

    return {
        "machine": machine_id.replace("_", "-"),
        "status": st["status"],
        "program": PROGRAMS[st["tick_count"] // 100 % len(PROGRAMS)],
        "spindleRpm": round(st["rpm"], 1),
        "spindleLoad": round(st["load"], 1),
        "feedRate": round(st["feed"], 1),
        "position": {
            "x": round(drift(0, 10, -500, 500), 1),
            "y": round(drift(0, 10, -500, 500), 1),
            "z": round(drift(0, 10, -500, 500), 1),
        },
        "toolNumber": (st["tick_count"] // 50) % max_tools + 1,
        "cycleTime": round((st["tick_count"] % 100) * settings.sim_tick_interval, 1),
        "partCount": st["part_count"],
        "powerKw": round((st["load"] / 100.0) * max_power, 2),
        "alarms": ["TOOL WEAR WARNING"] if st["status"] == "alarm" else []
    }


def update_haas_sim():
    st = sim_state["haas"]
    st["tick_count"] += 1

    r = random.random()
    if r < 0.05:
        st["status"] = "alarm"
    elif r < 0.20:
        st["status"] = "idle"
    else:
        st["status"] = "running"

    if st["status"] == "running":
        st["rpm"] = drift(st["rpm"], 50, 0, 6000)
        st["load"] = drift(st["load"], 2, 0, 100)
        st["feed"] = drift(st["feed"], 5, 0, 1000)
        if st["tick_count"] % 20 == 0:
            st["part_count"] += 1
    else:
        st["rpm"] = 0.0
        st["load"] = 0.0
        st["feed"] = 0.0

    return {
        "machine": "haas-tl1",
        "status": st["status"],
        "program": "O9999",
        "spindleRpm": round(st["rpm"], 1),
        "spindleLoad": round(st["load"], 1),
        "feedRate": round(st["feed"], 1),
        "position": {
            "x": round(drift(0, 5, -200, 200), 1),
            "z": round(drift(0, 5, -500, 500), 1),
        },
        "toolNumber": 1,
        "cycleTime": round((st["tick_count"] % 100) * settings.sim_tick_interval, 1),
        "partCount": st["part_count"],
        "powerKw": round((st["load"] / 100.0) * 7.5, 2),
        "coolant": st["status"] == "running",
        "alarms": ["SIMULATED ALARM"] if st["status"] == "alarm" else []
    }


def update_ur5e_sim():
    st = sim_state["ur5e"]
    
    for i in range(6):
        st["angles"][i] = drift(st["angles"][i], 1.0, -180.0, 180.0)
    
    for i in range(6):
        st["tcp"][i] = drift(st["tcp"][i], 2.0, -500.0, 500.0)

    joints = []
    labels = ["Base", "Shoulder", "Elbow", "Wrist 1", "Wrist 2", "Wrist 3"]
    for i in range(6):
        joints.append({
            "id": f"J{i+1}",
            "label": labels[i],
            "angle": round(st["angles"][i], 1),
            "speed": round(abs(drift(0, 2, -10, 10)), 1),
            "torque": round(abs(drift(0, 1, 0, 5)), 1)
        })

    return {
        "machine": "ur5e",
        "status": "running",
        "program": "sim_routine.urp",
        "robotMode": "RUNNING",
        "safetyMode": "NORMAL",
        "tcpPosition": {
            "x": round(st["tcp"][0], 1),
            "y": round(st["tcp"][1], 1),
            "z": round(st["tcp"][2], 1),
            "rx": round(st["tcp"][3], 1),
            "ry": round(st["tcp"][4], 1),
            "rz": round(st["tcp"][5], 1),
        },
        "tcpSpeed": round(drift(150, 10, 0, 300), 1),
        "speedFraction": 100.0,
        "joints": joints,
        "powerKw": 0.25,
        "voltage": 48.0,
        "current": 5.2,
        "alarms": [],
        "digitalOutputs": 0
    }


async def sim_tick_loop(state_manager):
    logger.info("Simulation tick loop started")
    while True:
        try:
            # Always update Makinos
            payload_a51nx = update_makino_sim("makino_a51nx", 8000, 14000, 22.0, 40)
            await state_manager.update_makino("makino_a51nx", payload_a51nx)

            payload_d200z = update_makino_sim("makino_d200z", 12000, 20000, 30.0, 30)
            await state_manager.update_makino("makino_d200z", payload_d200z)

            payload_ps95 = update_makino_sim("makino_ps95", 10000, 15000, 18.0, 24)
            await state_manager.update_makino("makino_ps95", payload_ps95)

            # Update Haas and UR5e if they are offline/simulated
            if state_manager.haas_bridge_status != "live":
                payload_haas = update_haas_sim()
                await state_manager.update_haas(payload_haas)

            if state_manager.ur5e_bridge_status != "live":
                payload_ur5e = update_ur5e_sim()
                await state_manager.update_ur5e(payload_ur5e)

        except Exception as e:
            logger.warning("Simulation tick error: %s", e)
            
        await asyncio.sleep(settings.sim_tick_interval)
