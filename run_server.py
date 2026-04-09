"""Entry point for the Ngwe Lwe API server.
Run this on the server machine:  python run_server.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",   # Accept connections from any LAN client
        port=8000,
        reload=False,
    )
