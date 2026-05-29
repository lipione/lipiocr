from fastapi import APIRouter

router = APIRouter(tags=["templates"])


@router.get("/__router_probe__/templates")
def templates_router_probe():
    return {"router": "templates"}
