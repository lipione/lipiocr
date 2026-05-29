from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/__router_probe__/health")
def health_router_probe():
    return {"router": "health"}
