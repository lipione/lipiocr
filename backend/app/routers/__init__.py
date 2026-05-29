from app.routers.health import router as health_router
from app.routers.integration_manifest import router as integration_manifest_router
from app.routers.templates import router as templates_router

__all__ = ["health_router", "integration_manifest_router", "templates_router"]
