import json
import logging
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import MutableHeaders

logger = logging.getLogger("booking.http")


class RequestMetricsMiddleware:
    def __init__(self, app, metrics):
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        start, status = perf_counter(), 500

        async def response_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, response_send)
        finally:
            duration = perf_counter() - start
            route = getattr(scope.get("route"), "path", "__unmatched__")
            if route != "/metrics":
                self.metrics.requests.labels(scope["method"], route, str(status)).inc()
                self.metrics.duration.labels(scope["method"], route).observe(duration)
            logger.info(
                json.dumps(
                    {
                        "request_id": request_id,
                        "method": scope["method"],
                        "route": route,
                        "status": status,
                        "duration_ms": round(duration * 1000, 3),
                    }
                )
            )
