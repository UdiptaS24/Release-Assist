from fastapi import FastAPI
from app.routers.release_router import router as release_router

app = FastAPI(title="Release Assist - MVP")
app.include_router(release_router)

@app.get("/")
async def root():
    return {"status": "healthy", "message": "Welcome to the Release Assist MVP API. Use the /releases endpoint to submit release requests."}