"""API routers for the pipe freeze-risk analyser."""

from .analysis import router as analysis_router

__all__ = ["analysis_router"]
