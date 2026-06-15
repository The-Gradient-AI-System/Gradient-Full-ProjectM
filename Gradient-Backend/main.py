import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes.userRoutes import router as user_router, users_router
from routes.gmailRoutes import router as gmail_router
from routes.settingsRoutes import router as settings_router
from routes.managerRoutes import router as manager_router
from routes.profileRoutes import router as profile_router
from routes.passwordResetRoutes import router as password_reset_router
from routes import emailRoutes
from routes.leadRoutes import router as lead_router
from service.autosyncService import auto_sync_loop
import asyncio

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
AVATARS_DIR = STATIC_DIR / "avatars"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://gradient-prod-test.vercel.app",
]

extra_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*default_origins, *extra_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(users_router)
app.include_router(gmail_router)
app.include_router(settings_router)
app.include_router(manager_router)
app.include_router(profile_router)
app.include_router(password_reset_router)
app.include_router(lead_router)
app.include_router(emailRoutes.router)
app.include_router(emailRoutes.emails_router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/health")
def health():
    return {"ok": True}


@app.on_event("startup")
async def startup():
    asyncio.create_task(auto_sync_loop())
