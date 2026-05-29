from fastapi import APIRouter

router = APIRouter(tags=["integration-manifest"])


@router.get("/__router_probe__/integration-manifest")
def integration_manifest_router_probe():
    return {"router": "integration-manifest"}
