from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "http_requests_total",
            "Completed HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["method", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry,
        )
        self.ready = Gauge(
            "app_ready", "Database-backed application readiness", registry=self.registry
        )
        self.created = Counter(
            "bookings_created_total", "Committed bookings", registry=self.registry
        )
        self.cancelled = Counter(
            "bookings_cancelled_total", "Committed cancellations", registry=self.registry
        )
        self.conflicts = Counter(
            "booking_conflicts_total", "Rejected overlapping bookings", registry=self.registry
        )
