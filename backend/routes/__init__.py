"""Route-модулі для логічного розбиття server.py."""
from .soldiers import router as soldiers_router
from .transfers import router as transfers_router
from .backup import router as backup_router
from .warehouse import router as warehouse_router

__all__ = ["soldiers_router", "transfers_router", "backup_router", "warehouse_router"]
