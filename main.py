import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers.api import router
from app.routers.clans import router as clans_router
from app.services import worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot = Bot(token=settings.bot_token)
    worker.set_bot(bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(worker.check_alerts, "interval", seconds=30)
    scheduler.start()

    yield

    scheduler.shutdown()
    await bot.session.close()


app = FastAPI(title="AUC BOT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def verify_app_token(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in ("/health",):
        return await call_next(request)
    token = request.headers.get("X-App-Token")
    if not token or token != settings.app_secret_token:
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    return await call_next(request)


app.include_router(router, prefix="/api")
app.include_router(clans_router, prefix="/api")


@app.get("/health")
async def health():
    return {"ok": True}
