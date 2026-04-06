"""
Incident scenarios for the Incident Response Triage environment.
Each scenario defines a realistic production incident with deterministic data.
"""

SERVICES = [
    "web-frontend", "api-gateway", "auth-service", "user-service",
    "order-service", "payment-service", "notification-service",
    "database", "cache", "message-queue",
]

DEPENDENCY_GRAPH = {
    "web-frontend": ["api-gateway"],
    "api-gateway": ["auth-service", "user-service", "order-service", "notification-service", "cache"],
    "auth-service": ["database", "cache"],
    "user-service": ["database", "cache"],
    "order-service": ["payment-service", "database", "message-queue"],
    "payment-service": ["database"],
    "notification-service": ["message-queue", "cache"],
    "database": [],
    "cache": [],
    "message-queue": [],
}

# ---------- helper to build a healthy service dict ----------
def _healthy(cpu=8, mem=25, lat=30, err=0, conn=20, dep=None):
    d = dict(cpu_percent=cpu, memory_percent=mem, request_latency_ms=lat,
             error_rate_percent=err, active_connections=conn, instances=1,
             uptime_hours=720.0, status="healthy", last_deployment=dep)
    return d


# ============================================================
#  SCENARIO 1  – Easy: Memory Leak in User Service
# ============================================================
EASY_SERVICES = {s: _healthy() for s in SERVICES}
EASY_SERVICES["user-service"] = dict(
    cpu_percent=45, memory_percent=92, request_latency_ms=850,
    error_rate_percent=12, active_connections=156, instances=1,
    uptime_hours=720, status="degraded", last_deployment="v1.8.2 (14 days ago)")
EASY_SERVICES["api-gateway"] = dict(
    cpu_percent=30, memory_percent=45, request_latency_ms=350,
    error_rate_percent=5, active_connections=80, instances=2,
    uptime_hours=720, status="degraded", last_deployment=None)

EASY_ALERTS = [
    dict(id="A1", severity="critical", service="user-service",
         message="Memory usage critical: 92% utilized, OOM risk imminent", timestamp="10:24:00"),
    dict(id="A2", severity="warning", service="user-service",
         message="Response latency p99 = 850ms (threshold 200ms)", timestamp="10:24:30"),
    dict(id="A3", severity="info", service="api-gateway",
         message="5% of requests returning 502 Bad Gateway", timestamp="10:25:00"),
]

EASY_LOGS = {
    "user-service": (
        "[10:23:45] WARN  Heap usage at 89%, GC frequency increasing\n"
        "[10:24:12] ERROR OutOfMemoryError in thread 'http-handler-23'\n"
        "[10:24:13] WARN  Request queue backing up, 156 pending requests\n"
        "[10:24:45] ERROR Failed to allocate buffer for user session cache\n"
        "[10:25:01] WARN  Memory leak suspected in SessionManager.getUserSessions()\n"
        "[10:25:30] INFO  GC pause time: 1243ms (threshold: 200ms)"
    ),
    "api-gateway": (
        "[10:24:00] WARN  Upstream user-service responding slowly: 850ms avg\n"
        "[10:24:15] ERROR 502 Bad Gateway for /api/users/* - upstream timeout\n"
        "[10:24:30] INFO  Circuit breaker HALF-OPEN for user-service\n"
        "[10:25:00] WARN  5.2% of requests failing with 502"
    ),
}

EASY_SCENARIO = dict(
    name="Memory Leak in User Service",
    max_steps=15,
    services=EASY_SERVICES,
    alerts=EASY_ALERTS,
    logs=EASY_LOGS,
    root_cause_service="user-service",
    root_cause_keywords=["memory", "leak", "oom", "heap", "out of memory"],
    remediation_action="RESTART",
    remediation_target="user-service",
    secondary_remediation=None,
    milestones={
        "investigated_root_service": 0.10,
        "investigated_context":     0.05,
        "correct_diagnosis":        0.25,
        "correct_remediation":      0.35,
        "incident_resolved":        0.25,
    },
    optimal_actions=[
        "CHECK_METRICS user-service",
        "INVESTIGATE user-service",
        "INVESTIGATE api-gateway",
        "DIAGNOSE memory leak in user-service",
        "RESTART user-service",
        "RESOLVE Fixed memory leak by restarting user-service",
    ],
)


# ============================================================
#  SCENARIO 2  – Medium: Database Connection Pool Exhaustion
# ============================================================
MED_SERVICES = {s: _healthy() for s in SERVICES}
MED_SERVICES["database"] = dict(
    cpu_percent=65, memory_percent=78, request_latency_ms=1200,
    error_rate_percent=8, active_connections=485, instances=1,
    uptime_hours=2160, status="degraded", last_deployment=None)
MED_SERVICES["order-service"] = dict(
    cpu_percent=25, memory_percent=40, request_latency_ms=3500,
    error_rate_percent=45, active_connections=35, instances=2,
    uptime_hours=720, status="down", last_deployment=None)
MED_SERVICES["payment-service"] = dict(
    cpu_percent=20, memory_percent=35, request_latency_ms=2800,
    error_rate_percent=30, active_connections=25, instances=1,
    uptime_hours=720, status="degraded", last_deployment=None)
MED_SERVICES["api-gateway"] = dict(
    cpu_percent=35, memory_percent=50, request_latency_ms=2500,
    error_rate_percent=20, active_connections=110, instances=2,
    uptime_hours=720, status="degraded", last_deployment=None)
MED_SERVICES["auth-service"] = dict(
    cpu_percent=15, memory_percent=30, request_latency_ms=800,
    error_rate_percent=8, active_connections=45, instances=1,
    uptime_hours=720, status="degraded", last_deployment=None)

MED_ALERTS = [
    dict(id="A1", severity="critical", service="order-service",
         message="Health check failing – 45% error rate on /api/orders", timestamp="14:10:05"),
    dict(id="A2", severity="critical", service="database",
         message="Connection pool near capacity: 485/500 active connections", timestamp="14:10:10"),
    dict(id="A3", severity="warning", service="api-gateway",
         message="Response time spike: p99 = 2.5s (threshold 500ms)", timestamp="14:10:15"),
    dict(id="A4", severity="warning", service="payment-service",
         message="Timeout errors increased to 30%", timestamp="14:10:20"),
    dict(id="A5", severity="info", service="auth-service",
         message="Occasional connection refused from database", timestamp="14:10:30"),
]

MED_LOGS = {
    "database": (
        "[14:10:05] WARN  Connection pool utilization at 97% (485/500)\n"
        "[14:10:12] ERROR Max connections reached, rejecting new connection from order-service\n"
        "[14:10:15] WARN  Slow query: SELECT * FROM orders WHERE... (4500ms)\n"
        "[14:10:30] ERROR Connection timeout for auth-service (pool exhausted)\n"
        "[14:11:00] WARN  Active transactions: 312, idle connections: 15\n"
        "[14:11:15] INFO  max_pool_size=500, recommended=1000 for current load"
    ),
    "order-service": (
        "[14:10:10] ERROR ConnectionTimeoutException: Cannot acquire DB connection within 30s\n"
        "[14:10:20] ERROR Order creation failed: database unavailable\n"
        "[14:10:35] WARN  Retry queue depth: 234 pending orders\n"
        "[14:10:50] ERROR Health check failed: unable to connect to database\n"
        "[14:11:00] WARN  Circuit breaker OPEN for database connection"
    ),
    "payment-service": (
        "[14:10:15] ERROR Database connection pool exhausted, cannot process payment\n"
        "[14:10:30] WARN  Payment verification timeout after 25s\n"
        "[14:10:45] ERROR Failed to record transaction: no available DB connections\n"
        "[14:11:00] INFO  Retrying database connection in 5s"
    ),
    "api-gateway": (
        "[14:10:20] WARN  Upstream order-service: 503 Service Unavailable\n"
        "[14:10:25] WARN  Upstream payment-service: 504 Gateway Timeout\n"
        "[14:10:30] ERROR 20% of requests returning 5xx errors\n"
        "[14:11:00] INFO  Circuit breaker HALF-OPEN for order-service"
    ),
}

MED_SCENARIO = dict(
    name="Database Connection Pool Exhaustion",
    max_steps=20,
    services=MED_SERVICES,
    alerts=MED_ALERTS,
    logs=MED_LOGS,
    root_cause_service="database",
    root_cause_keywords=["connection", "pool", "exhaust", "max connection", "database connection"],
    remediation_action="INCREASE_CONNECTIONS",
    remediation_target="database",
    secondary_remediation=None,
    milestones={
        "investigated_symptoms":    0.05,
        "investigated_root_service":0.10,
        "traced_dependencies":      0.05,
        "correct_diagnosis":        0.25,
        "correct_remediation":      0.30,
        "incident_resolved":        0.25,
    },
    optimal_actions=[
        "INVESTIGATE order-service",
        "CHECK_DEPENDENCIES order-service",
        "CHECK_METRICS database",
        "INVESTIGATE database",
        "DIAGNOSE database connection pool exhaustion",
        "INCREASE_CONNECTIONS database",
        "RESOLVE Fixed database connection pool exhaustion by increasing pool size",
    ],
)


# ============================================================
#  SCENARIO 3  – Hard: Cascading Deployment Failure
# ============================================================
HARD_SERVICES = {s: _healthy() for s in SERVICES}
HARD_SERVICES["payment-service"] = dict(
    cpu_percent=85, memory_percent=70, request_latency_ms=5000,
    error_rate_percent=78, active_connections=5, instances=1,
    uptime_hours=0.6, status="down", last_deployment="v2.3.1 deployed 35 min ago")
HARD_SERVICES["order-service"] = dict(
    cpu_percent=40, memory_percent=55, request_latency_ms=4200,
    error_rate_percent=60, active_connections=80, instances=2,
    uptime_hours=720, status="down", last_deployment=None)
HARD_SERVICES["api-gateway"] = dict(
    cpu_percent=50, memory_percent=55, request_latency_ms=3500,
    error_rate_percent=35, active_connections=200, instances=2,
    uptime_hours=720, status="degraded", last_deployment=None)
HARD_SERVICES["web-frontend"] = dict(
    cpu_percent=30, memory_percent=40, request_latency_ms=400,
    error_rate_percent=25, active_connections=300, instances=3,
    uptime_hours=720, status="degraded", last_deployment=None)
HARD_SERVICES["cache"] = dict(
    cpu_percent=10, memory_percent=85, request_latency_ms=5,
    error_rate_percent=0, active_connections=90, instances=1,
    uptime_hours=720, status="healthy", last_deployment=None)
HARD_SERVICES["notification-service"] = dict(
    cpu_percent=15, memory_percent=35, request_latency_ms=200,
    error_rate_percent=10, active_connections=30, instances=1,
    uptime_hours=720, status="degraded", last_deployment=None)

HARD_ALERTS = [
    dict(id="A1", severity="critical", service="web-frontend",
         message="User-facing errors at 25% – customer impact detected", timestamp="15:05:00"),
    dict(id="A2", severity="critical", service="order-service",
         message="60% error rate – checkout flow broken", timestamp="15:05:05"),
    dict(id="A3", severity="warning", service="api-gateway",
         message="5xx response rate at 35%", timestamp="15:05:10"),
    dict(id="A4", severity="warning", service="cache",
         message="Cache memory utilization elevated at 85%", timestamp="15:05:15"),
    dict(id="A5", severity="info", service="payment-service",
         message="v2.3.1 deployed 35 min ago by CI/CD pipeline", timestamp="15:04:30"),
    dict(id="A6", severity="info", service="notification-service",
         message="Elevated error notification delivery volume", timestamp="15:05:20"),
]

HARD_LOGS = {
    "web-frontend": (
        "[15:05:10] ERROR API call to /api/orders failed: 503 from api-gateway\n"
        "[15:05:15] ERROR Checkout page rendering error: upstream service unavailable\n"
        "[15:05:20] WARN  User-facing error rate trending up: 25% of page loads\n"
        "[15:05:30] INFO  Static assets and auth flows functioning normally\n"
        "[15:05:45] ERROR Customer complaint volume spike detected"
    ),
    "api-gateway": (
        "[15:05:05] ERROR Upstream order-service: 503 Service Unavailable\n"
        "[15:05:10] ERROR Upstream payment-service: 500 Internal Server Error\n"
        "[15:05:15] WARN  35% of routed requests returning 5xx\n"
        "[15:05:20] INFO  Routes to auth-service and user-service: normal\n"
        "[15:05:30] WARN  Circuit breaker OPEN for payment-service, HALF-OPEN for order-service"
    ),
    "order-service": (
        "[15:05:00] ERROR PaymentServiceException: payment validation failed HTTP 500\n"
        "[15:05:10] ERROR Cannot process order #45621: payment-service invalid response\n"
        "[15:05:15] WARN  Order processing halted: upstream payment dependency failing\n"
        "[15:05:20] ERROR Stack trace: PaymentClient.validatePayment() -> HTTP 500\n"
        "[15:05:30] INFO  Database connection healthy, internal logic OK"
    ),
    "payment-service": (
        "[15:04:30] INFO  Deployment v2.3.1 started by CI/CD pipeline\n"
        "[15:04:45] WARN  New deployment initializing payment processor module\n"
        "[15:05:00] ERROR NullPointerException in PaymentProcessor.processTransaction()\n"
        "[15:05:05] ERROR /validate endpoint returning HTTP 500\n"
        "[15:05:10] ERROR v2.3.1 introduced breaking change in PaymentConfig schema\n"
        "[15:05:20] CRITICAL Health check failing continuously since deployment\n"
        "[15:05:30] INFO  Previous stable version: v2.2.8"
    ),
    "cache": (
        "[15:05:00] INFO  Cache hit ratio: 78% (normal range)\n"
        "[15:05:10] WARN  Stale payment config entries found (from pre-deployment)\n"
        "[15:05:20] INFO  Memory at 85% – elevated but within safe range\n"
        "[15:05:30] INFO  Auto-eviction policy active, cleaning expired entries"
    ),
    "notification-service": (
        "[15:05:05] WARN  High volume of error notifications from order-service\n"
        "[15:05:10] INFO  Email notification queue depth: 456 pending\n"
        "[15:05:20] WARN  Some deliveries delayed due to queue backlog"
    ),
}

HARD_SCENARIO = dict(
    name="Cascading Deployment Failure",
    max_steps=25,
    services=HARD_SERVICES,
    alerts=HARD_ALERTS,
    logs=HARD_LOGS,
    root_cause_service="payment-service",
    root_cause_keywords=["deploy", "deployment", "rollback", "release", "v2.3.1", "regression", "bad deploy"],
    remediation_action="ROLLBACK",
    remediation_target="payment-service",
    secondary_remediation=("FLUSH_CACHE", None),
    milestones={
        "investigated_frontend":           0.05,
        "traced_to_backend":               0.05,
        "investigated_root_service":       0.10,
        "correct_diagnosis":               0.20,
        "correct_primary_remediation":     0.25,
        "correct_secondary_remediation":   0.10,
        "incident_resolved":               0.25,
    },
    optimal_actions=[
        "INVESTIGATE web-frontend",
        "INVESTIGATE api-gateway",
        "INVESTIGATE order-service",
        "INVESTIGATE payment-service",
        "DIAGNOSE bad deployment of payment-service v2.3.1",
        "ROLLBACK payment-service",
        "FLUSH_CACHE",
        "RESOLVE Rolled back payment-service to v2.2.8 and flushed stale cache",
    ],
)

# Master mapping
SCENARIOS = {
    "task_easy":   EASY_SCENARIO,
    "task_medium": MED_SCENARIO,
    "task_hard":   HARD_SCENARIO,
}
