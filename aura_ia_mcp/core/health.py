from fastapi import FastAPI

from .health_aggregator import HealthAggregator

# Global health aggregator instance
health_aggregator = HealthAggregator(cache_ttl=30)


def register_health_endpoints(app: FastAPI) -> None:
    @app.get("/health")
    async def health():
        """Basic health check."""
        return {"status": "ok"}

    @app.get("/healthz")
    async def healthz():
        """Kubernetes liveness probe - lightweight status check."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        """Kubernetes readiness probe - checks if service can accept traffic."""
        await health_aggregator.check_all()
        overall = health_aggregator.get_overall_status()

        if overall["status"] == "healthy":
            return {"status": "ready"}
        return {"status": "not_ready", "details": overall}

    @app.get("/health/detailed")
    async def detailed_health():
        """Detailed health check with all services."""
        await health_aggregator.check_all()
        return health_aggregator.get_overall_status()

    @app.get("/readiness")
    async def readiness():
        """Readiness check for Kubernetes."""
        await health_aggregator.check_all()
        overall = health_aggregator.get_overall_status()

        if overall["status"] == "healthy":
            return {"status": "ready"}
        return {"status": "not_ready", "details": overall}
