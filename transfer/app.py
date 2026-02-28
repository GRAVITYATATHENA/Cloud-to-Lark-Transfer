import asyncio
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from transfer.models import JobStore
from transfer.worker import run_job

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

def create_app(db_path: str = "jobs.db", store: JobStore = None) -> FastAPI:
    if store is None:
        store = JobStore(db_path)
    app = FastAPI(title="Cloud→LARK Transfer")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(request, "index.html")

    @app.post("/jobs")
    async def create_job(
        order_number: str = Form(...),
        source_url: str = Form(...),
    ):
        from transfer.config import Settings
        settings = Settings()
        job_id = await store.create_job(order_number=order_number, source_url=source_url)
        asyncio.create_task(run_job(job_id, store, settings))
        return {"job_id": job_id}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = await store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    return app

app = create_app()
