from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    haas_ip: str = "192.168.1.50"
    haas_port: int = 5051
    ur5e_ip: str = "192.168.1.15"
    ur5e_rtde_port: int = 30004
    ur5e_dashboard_port: int = 29999
    ur5e_script_port: int = 30001
    amcrest_ip: str = "192.168.1.108"
    amcrest_rtsp_user: str = "admin"
    amcrest_rtsp_pass: str = ""
    cam01_ingest_token: str = "makino-cam01"
    backend_port: int = 8000
    ur5e_http_api_key: str = "makino-lab"
    haas_poll_interval: float = 1.0
    ur5e_poll_interval: float = 0.1
    sim_tick_interval: float = 1.5
    reconnect_wait: float = 5.0
    dashboard_username: str = "admin"
    dashboard_password: str = "makino2024"

    model_config = {
        "env_file": str(Path(__file__).resolve().parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
