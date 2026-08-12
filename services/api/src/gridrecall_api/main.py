from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from gridrecall_api import __version__
from gridrecall_api.config import get_settings
from gridrecall_api.schemas import CustomRecommendationRequest, DemoState, Recommendation
from gridrecall_api.service import GridRecallDemoService, build_demo_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.demo = build_demo_service(settings)
    app.state.demo.open()
    try:
        yield
    finally:
        app.state.demo.close()


app = FastAPI(
    title="GridRecall API",
    description="Operational memory for distributed solar mini-grid maintenance.",
    version=__version__,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def demo_service(request: Request) -> GridRecallDemoService:
    return request.app.state.demo


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "version": __version__,
        "demo_mode": settings.demo_mode,
        "bedrock_enabled": bool(settings.bedrock_reasoning_model_id),
        "cockroach_enabled": bool(settings.database_url),
        "managed_mcp_enabled": bool(
            settings.cockroach_mcp_cluster_id and settings.cockroach_mcp_api_key
        ),
    }


@app.get("/api/demo", response_model=DemoState)
def get_demo(request: Request) -> DemoState:
    return demo_service(request).state()


@app.post("/api/demo/reset", response_model=DemoState)
def reset_demo(request: Request) -> DemoState:
    return demo_service(request).reset()


@app.post("/api/demo/incidents/first", response_model=DemoState)
def run_first_incident(request: Request) -> DemoState:
    return demo_service(request).run_first_incident()


@app.post("/api/demo/incidents/second", response_model=DemoState)
def run_second_incident(request: Request) -> DemoState:
    return demo_service(request).run_second_incident()


@app.post("/api/recommendations", response_model=Recommendation)
def recommend(payload: CustomRecommendationRequest, request: Request) -> Recommendation:
    return demo_service(request).recommend(payload.context, payload.technician_qualification)
