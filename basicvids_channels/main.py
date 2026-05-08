from contextlib import asynccontextmanager

from fastapi import FastAPI

from basicvids_channels.db import create_db_and_tables
from basicvids_channels.routers.channels import router as channels_router
from basicvids_channels.routers.root import router as root_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="BasicVids Channels", lifespan=lifespan)

app.include_router(channels_router, prefix="/api/v1")
app.include_router(root_router)
