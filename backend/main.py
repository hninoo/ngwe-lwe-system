from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.websocket_manager import ConnectionManager
from backend.routes import auth, accounts, services, transactions, dashboard, users, exchange_rates, reports, commission_tiers
from backend.routes import cashier


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Ngwe Lwe System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Desktop (PyQt6) clients — CORS not enforced by requests lib
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

ws_manager = ConnectionManager()

# Inject ws_manager into transactions route
transactions.ws_manager = ws_manager

app.include_router(auth.router)
app.include_router(services.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(exchange_rates.router)
app.include_router(reports.router)
app.include_router(commission_tiers.router)
app.include_router(cashier.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ws_clients": ws_manager.active_count}
