import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self):
        self.haas: dict = {}
        self.ur5e: dict = {}
        self.makino_a51nx: dict = {}
        self.makino_d200z: dict = {}
        self.makino_ps95: dict = {}
        self.haas_bridge_status: str = "offline"
        self.ur5e_bridge_status: str = "offline"
        self.on_update: Optional[Callable] = None

    async def update_haas(self, payload: dict):
        self.haas = payload
        await self._notify()

    async def update_ur5e(self, payload: dict):
        self.ur5e = payload
        await self._notify()

    async def update_makino(self, machine_id: str, payload: dict):
        if machine_id == "makino_a51nx":
            self.makino_a51nx = payload
        elif machine_id == "makino_d200z":
            self.makino_d200z = payload
        elif machine_id == "makino_ps95":
            self.makino_ps95 = payload
        else:
            logger.warning("Unknown makino machine_id: %s", machine_id)
            return
        await self._notify()

    def set_haas_bridge_status(self, status: str):
        self.haas_bridge_status = status

    def set_ur5e_bridge_status(self, status: str):
        self.ur5e_bridge_status = status

    def get_snapshot(self) -> dict:
        return {
            "haas": self.haas,
            "ur5e": self.ur5e,
            "makinoA51nx": self.makino_a51nx,
            "makinoD200Z": self.makino_d200z,
            "makinoPS95": self.makino_ps95,
            "bridgeStatus": {
                "haas": self.haas_bridge_status,
                "ur5e": self.ur5e_bridge_status,
            },
        }

    async def _notify(self):
        if self.on_update:
            await self.on_update(self.get_snapshot())


state_manager = StateManager()
