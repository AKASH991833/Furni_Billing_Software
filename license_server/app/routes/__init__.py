"""Routes package."""
from app.routes.activation import router as activation_router
from app.routes.admin import router as admin_router

__all__ = ["activation_router", "admin_router"]