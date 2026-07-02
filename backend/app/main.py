import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routes import auth, dead_letter, jobs, organizations, projects, queues, scheduled_jobs, workers
from app.config import settings
from app.core.exceptions import AppError

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Distributed Job Scheduler", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic puts the raw exception instance in ctx["error"] for validators that raise
    # ValueError directly (see JobCreate.validate_type_fields) -- not JSON-serializable as-is,
    # so stringify ctx values before returning.
    details = []
    for err in exc.errors():
        err = dict(err)
        if isinstance(err.get("ctx"), dict):
            err["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        details.append(err)
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"error": {"code": "validation_error", "message": "Invalid request", "details": details}}),
    )


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(projects.router)
app.include_router(queues.router)
app.include_router(jobs.router)
app.include_router(scheduled_jobs.router)
app.include_router(dead_letter.router)
app.include_router(workers.router)
