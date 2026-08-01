# -----------------------
# Defaults
# -----------------------

#: Default IBM Cloud Monitoring endpoint
DEFAULT_URL = ""

#: Default instance GUID
DEFAULT_GUID = ""

#: Default API key 
DEFAULT_APIKEY = ""

#: Sampling window parameters
BASELINE_MINUTES = 10
BASELINE_STEP = 60
ADAPT_MINUTES = 10
ADAPT_STEP_FAST = 10

#: Kubernetes namespace for deployment
NAMESPACE = ""

#: Default CSV log files
LOG_FILE = "multi_service_metrics.csv"
DERIVED_LOG_FILE = "multi_service_derived_metrics.csv"
UTILITY_LOG_FILE = "utility_log.csv"
AWARE_LOG_FILE = "aware_loop_log.csv"

#: Monitoring interval in seconds between runs
INTERVAL = 300

MAX_PODS = 5  # max pods to scale to

# -----------------------
# AWARE Framework Configuration
# -----------------------

"""
AWARE Framework: Assess, Weigh, Act, Reflect, Enrich
A modern, agentic alternative to MAPE-K loop
"""

# Agent communication settings
AGENT_TIMEOUT = 30  # seconds to wait for agent responses
AGENT_RETRY_COUNT = 3  # number of retries for failed agent calls

# Shared Knowledge Base configuration
KNOWLEDGE_BASE_PATH = "knowledge_base.db"
POLICY_LEARNING_RATE = 0.01
DISCOUNT_FACTOR = 0.95

# Reinforcement Learning configuration
RL_ENABLED = True
RL_EXPLORATION_RATE = 0.1  # epsilon for epsilon-greedy policy
RL_LEARNING_EPISODES = 100
RL_UPDATE_FREQUENCY = 10  # Update RL model every N cycles

# Reflection thresholds
REFLECTION_WINDOW = 5  # Number of past adaptations to analyze
SUCCESS_THRESHOLD = 0.8  # Minimum improvement to consider adaptation successful
DEGRADATION_THRESHOLD = -0.1  # Maximum allowed performance degradation

# Enrichment configuration
PATTERN_MINING_MIN_SUPPORT = 0.3
PATTERN_MINING_MIN_CONFIDENCE = 0.7


# -----------------------
# Metric Catalog
# -----------------------

"""
This section defines curated Sysdig metrics grouped into categories
(System, Application, JVM, Network, Storage, Kubernetes).

Each metric includes:
    - id: Sysdig metric identifier
    - aggregations: aggregation method over time and group

These definitions form the basis for monitoring, analysis, and plotting.
"""


# ===============================
# SYSTEM RESOURCES
# ===============================

SYSTEM_GAUGES = [
    {"id": "cpu.used.percent", "aggregations": {"time": "max", "group": "max"}},     # Peak CPU → hotspots/throttling risk (self-optimizing)
    {"id": "cpu.idle.percent", "aggregations": {"time": "min", "group": "min"}},     # Min idle → capacity saturation (self-optimizing)

    {"id": "memory.used.percent", "aggregations": {"time": "max", "group": "max"}},  # Peak memory → OOM risk (self-optimizing)
    {"id": "memory.swap.used.percent", "aggregations": {"time": "avg", "group": "avg"}},  # Swap pressure (self-optimizing)

    {"id": "fs.used.percent", "aggregations": {"time": "avg", "group": "avg"}},      # Disk usage % (self-optimizing)
    {"id": "fs.largest.used.percent", "aggregations": {"time": "max", "group": "max"}},  # Largest FS hotspot (self-optimizing)
    {"id": "fs.inodes.used.percent", "aggregations": {"time": "max", "group": "max"}},   # Inode exhaustion risk (self-configuring)

    {"id": "load.average.1m", "aggregations": {"time": "avg", "group": "avg"}},      # Short-term load (self-optimizing)
    {"id": "load.average.5m", "aggregations": {"time": "avg", "group": "avg"}},      # Mid-term load (self-optimizing)

    {"id": "cpu.system.percent", "aggregations": {"time": "avg", "group": "avg"}},   # Kernel CPU load (self-optimizing)
    {"id": "cpu.user.percent",   "aggregations": {"time": "avg", "group": "avg"}},   # User-space CPU load (self-optimizing)
    {"id": "cpu.iowait.percent", "aggregations": {"time": "avg", "group": "avg"}},   # IO wait → storage bottleneck (self-optimizing)
    {"id": "fd.used.percent",    "aggregations": {"time": "max", "group": "max"}},   # File descriptor exhaustion (self-configuring)
]

SYSTEM_COUNTERS = [
    {"id": "proc.count", "aggregations": {"time": "sum", "group": "sum"}},        # Running processes → capacity (self-configuring)
    {"id": "thread.count", "aggregations": {"time": "sum", "group": "sum"}},      # OS threads total (self-configuring)
    {"id": "syscall.count", "aggregations": {"time": "sum", "group": "sum"}},     # Syscalls over window → pressure (self-optimizing)

    {"id": "file.error.total.count", "aggregations": {"time": "sum", "group": "sum"}},  # FS errors over interval (self-configuring)
    {"id": "host.error.count",       "aggregations": {"time": "sum", "group": "sum"}},  # Host-level errors (self-configuring)
    {"id": "system.uptime",          "aggregations": {"time": "max", "group": "max"}},  # Node uptime (self-configuring)
]


# ===============================
# APPLICATION
# ===============================

APP_GAUGES = [
    {"id": "net.http.request.time", "aggregations": {"time": "max", "group": "max"}},  # Tail latency (self-optimizing)
]

APP_COUNTERS = [
    {"id": "net.http.request.count", "aggregations": {"time": "sum", "group": "sum"}},        # Total HTTP requests (self-optimizing)
    {"id": "net.http.error.count", "aggregations": {"time": "sum", "group": "sum"}},          # Total HTTP errors (self-optimizing)
    {"id": "net.http.statuscode.error.count", "aggregations": {"time": "sum", "group": "sum"}},  # Errors by status code (self-optimizing)

    {"id": "net.sql.request.count",     "aggregations": {"time": "sum", "group": "sum"}},     # SQL requests (self-optimizing)
    {"id": "net.sql.error.count",       "aggregations": {"time": "sum", "group": "sum"}},     # SQL errors (self-optimizing)
    {"id": "net.mongodb.request.count", "aggregations": {"time": "sum", "group": "sum"}},     # Mongo requests (self-optimizing)
    {"id": "net.mongodb.error.count",   "aggregations": {"time": "sum", "group": "sum"}},     # Mongo errors (self-optimizing)
]


# ===============================
# JAVA RUNTIME
# ===============================

JVM_GAUGES = [
    {"id": "jvm.heap.used.percent", "aggregations": {"time": "avg", "group": "avg"}},       # Heap usage % (self-optimizing)
    {"id": "jvm.nonHeap.used.percent", "aggregations": {"time": "avg", "group": "avg"}},    # Non-heap usage % (self-optimizing)
    {"id": "jvm.thread.count", "aggregations": {"time": "avg", "group": "avg"}},            # JVM thread count (self-optimizing)
    {"id": "jvm.heap.max",     "aggregations": {"time": "max", "group": "max"}},            # Heap capacity (self-optimizing)
]

JVM_COUNTERS = [
    {"id": "jvm.class.loaded", "aggregations": {"time": "sum", "group": "sum"}},     # Classes loaded total (self-configuring)
    {"id": "jvm.class.unloaded", "aggregations": {"time": "sum", "group": "sum"}},   # Classes unloaded total (self-configuring)
]


# ===============================
# NETWORK
# ===============================

NETWORK_COUNTERS = [
    {"id": "net.bytes.in", "aggregations": {"time": "sum", "group": "sum"}},          # Total ingress bytes (self-optimizing)
    {"id": "net.bytes.out", "aggregations": {"time": "sum", "group": "sum"}},         # Total egress bytes (self-optimizing)
    {"id": "net.connection.count.total", "aggregations": {"time": "max", "group": "max"}},  # Peak connections (self-optimizing)
    {"id": "net.error.count", "aggregations": {"time": "sum", "group": "sum"}},       # Network errors (self-configuring)
    {"id": "net.request.count", "aggregations": {"time": "sum", "group": "sum"}},     # Total requests (self-optimizing)
    {"id": "net.tcp.queue.len", "aggregations": {"time": "max", "group": "max"}},     # TCP backlog length (self-optimizing)
]


# ===============================
# STORAGE
# ===============================

STORAGE_GAUGES = [
    {"id": "fs.bytes.used", "aggregations": {"time": "sum", "group": "sum"}},     # Total used bytes (self-optimizing)
    {"id": "fs.free.percent", "aggregations": {"time": "min", "group": "min"}},   # Lowest free % → risk (self-optimizing)
]


# ===============================
# KUBERNETES / CLUSTER
# ===============================

K8S_GAUGES = [
    {"id": "kubernetes.pod.status.ready", "aggregations": {"time": "avg", "group": "avg"}},        # Pod readiness ratio (self-configuring)
    {"id": "kubernetes.deployment.replicas.running", "aggregations": {"time": "avg", "group": "avg"}},  # Running replicas (self-configuring)
    {"id": "kubernetes.node.ready", "aggregations": {"time": "avg", "group": "avg"}},              # Node health ratio (self-configuring)
    {"id": "kubernetes.node.memoryPressure", "aggregations": {"time": "max", "group": "max"}},     # Any node under memory pressure (self-configuring)
    {"id": "kubernetes.statefulSet.status.replicas.ready", "aggregations": {"time": "avg", "group": "avg"}},  # StatefulSet readiness (self-configuring)
]

K8S_COUNTERS = [
    {"id": "kubernetes.pod.restart.count", "aggregations": {"time": "sum", "group": "sum"}},  # Pod restarts (self-configuring)
    {"id": "kubernetes.job.numFailed", "aggregations": {"time": "sum", "group": "sum"}},      # Failed jobs (self-configuring)
]

# ===============================
# COST
# ===============================

COST_METRICS = [
    # Node-level total cost (aggregates compute + memory + overhead)
    # Self-configuring → used to balance performance vs budget at cluster level
    {"id": "sysdig.cost.sysdig_costs_node_cost_total", "aggregations": {"time": "sum", "group": "sum"}},

    # CPU usage cost for workloads (tracks actual $ spent on CPU utilization)
    # Self-optimizing → highlights inefficiency if CPU cost grows faster than throughput
    {"id": "sysdig.cost.sysdig_costs_workload_cpu_used_cost_total", "aggregations": {"time": "sum", "group": "sum"}},

    # Memory usage cost for workloads (tracks actual $ spent on memory utilization)
    # Self-configuring → used to tune vertical scaling vs adding pods
    {"id": "sysdig.cost.sysdig_costs_workload_memory_used_cost_total", "aggregations": {"time": "sum", "group": "sum"}},

    # Storage cost for workloads (tracks $ spent on persistent storage usage)
    # Self-configuring → helps detect when scaling services leads to unsustainable storage costs
    {"id": "sysdig.cost.sysdig_costs_workload_storage_used_cost_total", "aggregations": {"time": "sum", "group": "sum"}},
]


# ===============================
# Aggregate Metric List
# ===============================

METRICS = (
    SYSTEM_GAUGES + SYSTEM_COUNTERS +
    APP_GAUGES + APP_COUNTERS +
    JVM_GAUGES + JVM_COUNTERS +
    NETWORK_COUNTERS +
    STORAGE_GAUGES +
    K8S_GAUGES + K8S_COUNTERS +
    COST_METRICS
)


# ===============================
# Derived Metrics
# ===============================

"""
Derived metrics computed from raw Sysdig metrics.
Each function takes a dictionary of raw metric values and returns a computed value.
"""

DERIVED_METRICS = {
    # HTTP error rate
    "http.error.rate": lambda d: (
        d.get("net.http.error.count", 0) / max(d.get("net.http.request.count", 1), 1)
    ),
    
    # Average HTTP latency (ms)
    "http.latency": lambda d: d.get("net.http.request.time", 0),
    
    # Throughput (requests per second) - assumes 60s window
    "http.throughput": lambda d: d.get("net.http.request.count", 0) / 60.0,
    
    # Cost per request (dollars)
    "cost.per.request": lambda d: (
        (d.get("sysdig.cost.sysdig_costs_workload_cpu_used_cost_total", 0) +
         d.get("sysdig.cost.sysdig_costs_workload_memory_used_cost_total", 0) +
         d.get("sysdig.cost.sysdig_costs_workload_storage_used_cost_total", 0)) /
        max(d.get("net.http.request.count", 1), 1)
    ),
}

# Thresholds for derived metrics used in planning
THRESHOLDS = {
    "http.error.rate": 0.05,      # Max 5% error rate
    "http.latency": 1000,          # Max 1000ms latency
    "http.throughput": 10,         # Min 10 req/s
    "cost.per.request": 0.001,    # Max $0.001 per request
}


# -----------------------
# SLO Thresholds
# -----------------------

"""
Service Level Objectives (SLOs) represented as threshold rules.
Format: metric_id -> (direction, threshold)
    - direction: "gt" (greater than) or "lt" (less than)
    - threshold: numeric boundary value
"""

SLO_THRESHOLDS = {
    "cpu.used.percent": ("gt", 85.0),
    "cpu.idle.percent": ("lt", 10.0),
    "cpu.iowait.percent": ("gt", 20.0),
    "memory.used.percent": ("gt", 85.0),
    "memory.swap.used.percent": ("gt", 20.0),
    "fs.used.percent": ("gt", 85.0),
    "fd.used.percent": ("gt", 90.0),

    "net.http.request.time": ("gt", 500.0),
    "net.http.error.count": ("gt", 50.0),
    "net.http.statuscode.error.count": ("gt", 50.0),
    "net.sql.error.count": ("gt", 10.0),
    "net.mongodb.error.count": ("gt", 10.0),

    "jvm.heap.used.percent": ("gt", 80.0),
    "jvm.nonHeap.used.percent": ("gt", 80.0),
    "jvm.thread.count": ("gt", 1000),

    "net.connection.count.total": ("gt", 8000),
    "net.error.count": ("gt", 100.0),
    "net.tcp.queue.len": ("gt", 500.0),

    "fs.free.percent": ("lt", 15.0),

    "kubernetes.pod.status.ready": ("lt", 0.9),
    "kubernetes.deployment.replicas.running": ("lt", 0.9),
    "kubernetes.node.ready": ("lt", 0.9),
    "kubernetes.node.memoryPressure": ("gt", 0.0),
    "kubernetes.statefulSet.status.replicas.ready": ("lt", 0.9),
    "kubernetes.pod.restart.count": ("gt", 5.0),
    "kubernetes.job.numFailed": ("gt", 3.0),

    "fs.largest.used.percent": ("gt", 85.0),
    "fs.inodes.used.percent": ("gt", 90.0),
    "load.average.1m": ("gt", 2.0),
    "load.average.5m": ("gt", 1.5),
    "proc.count": ("gt", 3000),
    "thread.count": ("gt", 8000),
    "syscall.count": ("gt", 5e5),
    "file.error.total.count": ("gt", 0.0),
    "host.error.count": ("gt", 0.0),
    "system.uptime": ("lt", 60.0),  # alert if uptime < 60s (just rebooted)
    "net.http.request.count": ("gt", 1e6),
    "net.sql.request.count": ("gt", 1e6),
    "net.mongodb.request.count": ("gt", 1e6),
    "jvm.heap.max": ("lt", 128.0),  # arbitrary MB lower bound for small heap
    "jvm.class.loaded": ("gt", 1e5),
    "jvm.class.unloaded": ("gt", 1e5),
    "net.bytes.in": ("gt", 1e9),   # 1GB in window
    "net.bytes.out": ("gt", 1e9),
    "net.request.count": ("gt", 1e6),
    "fs.bytes.used": ("gt", 1e9),  # >1GB 
    
    "sysdig.cost.sysdig_costs_node_cost_total": ("lt", 100.0),       # Node cost <$100 in window
    "sysdig.cost.sysdig_costs_workload_cpu_used_cost_total": ("lt", 50.0),   # CPU cost <$50
    "sysdig.cost.sysdig_costs_workload_memory_used_cost_total": ("lt", 50.0),# Memory cost <$50
    "sysdig.cost.sysdig_costs_workload_storage_used_cost_total": ("lt", 20.0),# Storage cost <$20

    "http.error.rate": ("lt", 0.05),   # <5% errors
    "cost.per.request": ("lt", 0.01),  # <$0.01 per request
}


# -----------------------
# Severity Mapping
# -----------------------

"""
Syslog severity scale (RFC 5424):
    0 = Emergency
    1 = Alert
    2 = Critical
    3 = Error
    4 = Warning
    5 = Notice
    6 = Info
    7 = Debug
"""

METRIC_SEVERITY = {
    "cpu.used.percent": 3,
    "cpu.idle.percent": 5,
    "cpu.iowait.percent": 2,
    "memory.used.percent": 2,
    "memory.swap.used.percent": 2,
    "fs.used.percent": 2,
    "fs.free.percent": 1,
    "fd.used.percent": 2,

    "net.http.error.count": 1,
    "net.http.statuscode.error.count": 1,
    "file.error.total.count": 1,
    "host.error.count": 1,
    "net.error.count": 1,
    "kubernetes.job.numFailed": 1,

    "kubernetes.pod.status.ready": 3,
    "kubernetes.pod.restart.count": 2,
    "kubernetes.node.ready": 2,
    "kubernetes.node.memoryPressure": 1,

    "fs.largest.used.percent": 2,
    "fs.inodes.used.percent": 2,
    "load.average.1m": 4,
    "load.average.5m": 4,
    "proc.count": 3,
    "thread.count": 3,
    "syscall.count": 4,
    "file.error.total.count": 1,
    "host.error.count": 1,
    "system.uptime": 5,
    "net.http.request.count": 6,
    "jvm.heap.max": 5,
    "jvm.class.loaded": 5,
    "jvm.class.unloaded": 5,
    "net.bytes.in": 6,
    "net.bytes.out": 6,
    "net.request.count": 6,
    "fs.bytes.used": 2,

    "sysdig.cost.sysdig_costs_node_cost_total": 2,        
    "sysdig.cost.sysdig_costs_workload_cpu_used_cost_total": 2,
    "sysdig.cost.sysdig_costs_workload_memory_used_cost_total": 2,
    "sysdig.cost.sysdig_costs_workload_storage_used_cost_total": 3, 

    "http.error.rate": 1,    
    "cost.per.request": 2,
}


# -----------------------
# Category Map
# -----------------------

"""
Mapping from high-level categories (system, application, jvm, network, storage, kubernetes)
to their constituent metric IDs. Used to compute category-level utility.
"""

CATEGORY_MAP = {
    "system": [
        "cpu.used.percent", "cpu.idle.percent", "cpu.system.percent", "cpu.user.percent",
        "cpu.iowait.percent", "memory.used.percent", "memory.swap.used.percent",
        "fs.used.percent", "fs.largest.used.percent", "fs.inodes.used.percent",
        "load.average.1m", "load.average.5m", "fd.used.percent", "proc.count",
        "thread.count", "syscall.count"
    ],
    "application": [
        "net.http.request.time", "net.http.error.count",
        "net.http.statuscode.error.count", "net.sql.error.count",
        "net.mongodb.error.count", "http.error.rate"
    ],
    "jvm": [
        "jvm.heap.used.percent", "jvm.nonHeap.used.percent", "jvm.thread.count",
        "jvm.heap.max", "jvm.class.loaded", "jvm.class.unloaded"
    ],
    "network": [
        "net.bytes.in", "net.bytes.out", "net.connection.count.total",
        "net.error.count", "net.request.count", "net.tcp.queue.len"
    ],
    "storage": [
        "fs.bytes.used", "fs.free.percent"
    ],
    "kubernetes": [
        "kubernetes.pod.status.ready", "kubernetes.deployment.replicas.running",
        "kubernetes.node.ready", "kubernetes.node.memoryPressure",
        "kubernetes.statefulSet.status.replicas.ready", "kubernetes.pod.restart.count",
        "kubernetes.job.numFailed"
    ],
    "cost": [
        "sysdig.cost.sysdig_costs_node_cost_total",
        "sysdig.cost.sysdig_costs_workload_cpu_used_cost_total",
        "sysdig.cost.sysdig_costs_workload_memory_used_cost_total",
        "sysdig.cost.sysdig_costs_workload_storage_used_cost_total",
        "cost.per.request"
    ],
}

# -----------------------
# Utility History
# -----------------------

#: Exponential Moving Average (EMA) history for utility smoothing
UTILITY_HISTORY = {
    "overall": None,
    "categories": {cat: None for cat in CATEGORY_MAP.keys()}
}
