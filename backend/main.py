import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import get_current_user
from backend.database import init_db
from backend.websocket_manager import ConnectionManager, TicketStore
from backend.routes import auth, accounts, transactions, dashboard, users, exchange_rates, reports, commission_tiers
from backend.routes import cashier, reconciliation
from backend.routes import companies, service_types, activity_logs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure assets/logos/ directory exists and is writable
    logos_dir = Path("assets/logos")
    logos_dir.mkdir(parents=True, exist_ok=True)
    logo_env_fallback = os.environ.get("LOGO_DIR", "")
    if not os.access(str(logos_dir), os.W_OK):
        logger.warning(
            "assets/logos/ directory is not writable. "
            "Logo uploads will fail. LOGO_DIR env fallback: %s",
            logo_env_fallback or "(not set)",
        )
    init_db()
    yield


app = FastAPI(title="Ngwe Lwe", version="1.0.0-beta", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Desktop (PyQt6) clients — CORS not enforced by requests lib
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

ws_manager = ConnectionManager()
ticket_store = TicketStore(ttl=30)

# Inject ws_manager into transactions route
transactions.ws_manager = ws_manager

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(service_types.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(exchange_rates.router)
app.include_router(reports.router)
app.include_router(commission_tiers.router)
app.include_router(activity_logs.router)
app.include_router(cashier.router)
app.include_router(reconciliation.router)


@app.post("/ws-ticket")
def get_ws_ticket(current_user: dict = Depends(get_current_user)) -> dict:
    """Issue a short-lived one-time ticket for WebSocket auth (avoids JWT in logs)."""
    return {"ticket": ticket_store.issue()}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, ticket: str = "") -> None:
    if not ticket or not ticket_store.consume(ticket):
        await websocket.close(code=1008, reason="Invalid or expired ticket")
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ws_clients": ws_manager.active_count}
