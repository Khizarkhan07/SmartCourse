from prometheus_client import Counter, Histogram

enrollments_total = Counter(
    "enrollments_total",
    "Total number of enrollment workflows successfully started",
)

completions_total = Counter(
    "completions_total",
    "Total number of course completion workflows successfully started",
)

# 'workflow' label distinguishes which workflow type failed
workflow_failures_total = Counter(
    "workflow_failures_total",
    "Total number of workflow start failures by workflow type",
    ["workflow"],
)

# Buckets cover sub-second fast paths up to 60s for slow email/DB activities
workflow_duration_seconds = Histogram(
    "workflow_duration_seconds",
    "End-to-end workflow execution time from Temporal start to close",
    ["workflow"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)
