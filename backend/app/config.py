"""Application configuration using environment variables."""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Allsolve API credentials
    qs_access_key: str = ""
    qs_secret_key: str = ""
    qs_host: str = "https://allsolve.quanscient.com"

    # Application settings
    app_name: str = "Pipe Freeze-Risk Analyser"
    debug: bool = False

    # Analysis settings
    # Outside temperatures (°C) swept to find the critical temperature; the
    # user's outside temperature is always added.
    sweep_ambients_c: List[float] = [-5.0, -10.0, -15.0, -20.0, -25.0]
    # Allsolve simulation job time limit (fast-start nodes allow up to 15 min)
    sim_max_run_time_minutes: int = 15
    # Don't delete projects whose simulation failed, so the job log and setup
    # can be inspected in the Allsolve dashboard
    keep_failed_projects: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
