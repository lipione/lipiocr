import importlib


def test_production_router_modules_export_fastapi_router():
    module_names = [
        "app.routers.health",
        "app.routers.integration_manifest",
        "app.routers.templates",
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        assert hasattr(module, "router")
        assert module.router.routes
