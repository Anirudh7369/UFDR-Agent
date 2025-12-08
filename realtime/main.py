from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.analytics import router as analytics_router
from utils.db import init_db_pool, close_db_pool
from dotenv import load_dotenv
from api.uploads.routes import router as uploads_router
from contextlib import asynccontextmanager

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for database connection management"""
    # Startup
    await init_db_pool()
    yield
    # Shutdown
    await close_db_pool()


app = FastAPI(
    title="UFDR Real-time API",
    description="Real-time analytics API for UFDR Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analytics_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(ufdr_report_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "UFDR Real-time API is running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("realtime.main:app", host="0.0.0.0", port=8000, reload=True)
