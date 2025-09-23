from fastapi import FastAPI
from api.analytics import router as analytics_router
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="UFDR Real-time API",
    description="Real-time analytics API for UFDR Agent",
    version="1.0.0"
)

# Include the analytics router
app.include_router(analytics_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "UFDR Real-time API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)