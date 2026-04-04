import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers.api import router
from app.services import worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # init bot
    bot = Bot(token=settings.bot_token)
    worker.set_bot(bot)

    # start scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(worker.check_alerts, "interval", seconds=30)
    scheduler.start()

    yield

    scheduler.shutdown()
    await bot.session.close()


app = FastAPI(title="AUC BOT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # поменяй на домен фронта в проде
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"ok": True}
