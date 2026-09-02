"""Demo / trial control-plane constants.

Demo usage limits are intentionally separate from commercial entitlements.
They cap expensive demonstration actions, not ordinary reading.
"""
from __future__ import annotations

DEMO_ORGANIZATION_SLUG = "forestwatch-demo"
DEMO_ORGANIZATION_NAME = "ForestWatch Demonstration"
DEMO_ORGANIZATION_KIND = "demo"

DEMO_INTEL_COLLECTION = "demo_intelligence_events"
DEMO_SESSION_COLLECTION = "demo_sessions"
DEMO_PRODUCT_EVENT_COLLECTION = "demo_product_events"

DEMO_TOKEN_TYPE = "demo"
DEMO_USER_PROVIDER = "demo"
DEMO_VISITOR_EMAIL = "demo@forestwatch.local"
DEMO_VISITOR_NAME = "Demonstration visitor"

DEMO_CATALOG_FLAG = "demo_catalog"
DEMO_SESSION_HOURS = 4

# Ordinary navigation is unlimited. These meters cover meaningful actions only.
DEFAULT_DEMO_BUDGET: dict[str, int] = {
    "investigation": 5,
    "report": 2,
    "alert_simulation": 2,
    "intelligence_query": 10,
}

DEMO_REQUESTS_PER_MINUTE = 120
DEMO_MAX_BODY_BYTES = 65_536

GUIDE_STEPS: tuple[dict[str, str], ...] = (
    {
        "id": "forests",
        "title": "Your monitored forests",
        "body": "These are the stands ForestWatch is watching in this demonstration.",
    },
    {
        "id": "changed",
        "title": "What changed",
        "body": "Disturbance signals appear on the map when something in a watched forest looks different.",
    },
    {
        "id": "attention",
        "title": "What requires attention",
        "body": "The queue is ordered by investigation priority — not every observation is urgent.",
    },
    {
        "id": "investigate",
        "title": "Investigate",
        "body": "Open a disturbance to separate what was observed from what ForestWatch infers.",
    },
    {
        "id": "evidence",
        "title": "Review evidence",
        "body": "Evidence is shown separately from inference. Nothing here proves illegal activity.",
    },
    {
        "id": "alert",
        "title": "Set an alert",
        "body": "Simulate a notification to see how ForestWatch would tell your organization.",
    },
    {
        "id": "monitor",
        "title": "Monitor continuously",
        "body": "Create an organization to watch your own forests with the same workflow.",
    },
)
