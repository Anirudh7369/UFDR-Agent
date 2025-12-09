from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.analytics import router as analytics_router
from utils.db import init_db_pool, close_db_pool
from utils.redis import init_redis_pool, close_redis_pool
from dotenv import load_dotenv
from api.uploads.routes import router as uploads_router
from contextlib import asynccontextmanager
from pathlib import Path

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for DB and Redis connection management"""
    # Startup
    await init_db_pool()
    await init_redis_pool()
    yield
    # Shutdown
    await close_redis_pool()
    await close_db_pool()

app = FastAPI(
    title="UFDR Real-time API",
    description="Real-time analytics API for UFDR Agent",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the analytics router
app.include_router(analytics_router, prefix="/api")

app.include_router(uploads_router)

# Mount static files for serving visualizations
# Create the visualization directory if it doesn't exist
viz_dir = Path("forensic_visualizations")
viz_dir.mkdir(exist_ok=True)

app.mount("/static/visualizations", StaticFiles(directory=str(viz_dir)), name="visualizations")

@app.get("/")
async def root():
    return {"message": "UFDR Real-time API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)