"""
MTG Deck Upgrade Assistant — FastAPI Application Entry Point.

Run with:
    uvicorn app.main:app --reload
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.router import api_router
from app.config import get_settings
from app.database.session import init_db

settings = get_settings()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Help MTG Commander players find relevant cards from new expansions.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# API routes
app.include_router(api_router)

# ---------------------------------------------------------------------------
# Page routes (HTML)
# ---------------------------------------------------------------------------
@app.get("/", tags=["Pages"])
async def home_page(request: Request):
    """Main page with set sidebar and card grid."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/decks", tags=["Pages"])
async def decks_page(request: Request):
    """Commander decks analysis page."""
    return templates.TemplateResponse("decks.html", {"request": request})

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "app": settings.app_name}
