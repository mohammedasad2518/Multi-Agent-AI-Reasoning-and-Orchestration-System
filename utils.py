import os
import datetime
from typing import List, Tuple

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter


import subprocess
from sdcclient import SdMonitorClient, IbmAuthHelper

from constants import *

"""
Utility Functions for Sysdig Monitoring

This module provides general-purpose helper functions for the monitoring driver,
including:

    - Sysdig client initialization (IBM Cloud authentication).
    - Kubernetes pod discovery (via kubectl).
    - Service name normalization (strip random suffixes).
    - Time window construction for metric queries.
    - Tabular printing of metric results for console inspection.
    - Time-series plotting of metrics into PNG charts.

These utilities are used by the driver to support the Monitoring
and Analyzing phases of the MAPE-K loop (ECE 750 Assignment 1).
"""


def get_client(url: str, apikey: str, guid: str) -> SdMonitorClient:
    """
    Initialize and return an authenticated Sysdig Monitor client using IBM Cloud credentials.

    This function uses the IBM authentication helper to generate headers required
    for authenticating requests to IBM Cloud Monitoring with Sysdig. It then
    initializes a Sysdig Monitor client with those headers.

    Args:
        url (str): The Sysdig endpoint URL (typically IBM Cloud Monitoring endpoint).
        apikey (str): IBM Cloud API key used for authentication.
        guid (str): IBM Cloud Monitoring instance GUID.

    Returns:
        SdMonitorClient: A client object that can be used to query metrics and interact
        with the Sysdig Monitor API.
    """
    # Build authentication headers using IBM Cloud API key + GUID
    headers = IbmAuthHelper.get_headers(url, apikey, guid)

    # Initialize and return Sysdig client with those headers
    return SdMonitorClient(sdc_url=url, custom_headers=headers)


def get_pods(namespace: str) -> list[str]:
    """
    Retrieve all pod names in a specific Kubernetes namespace.

    This function runs the `kubectl get pods` command with JSONPath to extract
    pod names directly, ensuring minimal parsing overhead. It captures the output
    and returns a list of pod names as plain strings.

    Args:
        namespace (str): The Kubernetes namespace to query for pods.

    Returns:
        list[str]: A list of pod names (strings) in the given namespace.

    Raises:
        subprocess.CalledProcessError: If the `kubectl` command fails (e.g., invalid namespace).
    """
    # Run kubectl to get pods in JSONPath form (only pod names)
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "jsonpath={.items[*].metadata.name}"],
        capture_output=True, text=True, check=True
    )
    # Split the space-separated pod names into a list
    return result.stdout.strip().split()


def normalize_service_name(pod_name: str) -> str:
    """
    Derive a simplified service name from a full Kubernetes pod name.

    Pod names often contain suffixes such as random hashes or instance IDs
    (e.g., 'acmeair-flight-db-afdaljfarueo'). This function strips such suffixes
    to obtain a cleaner, stable identifier for the service. 

    Args:
        pod_name (str): The raw pod name as reported by Kubernetes.

    Returns:
        str: A normalized service name, typically the pod name without its
        trailing hash-like suffix.
    
    Examples:
        >>> normalize_service_name("acmeair-flight-db-afdaljfarueo")
        'acmeair-flight-db'
    """

    # Split the name by hyphen (conventionally separates service + hash)
    parts = pod_name.split("-")

    return "-".join(parts[:-2])
    

def build_time_window(last_seconds: int = 600) -> Tuple[int, int]:
    """
    Construct a relative time window for Sysdig metric queries.

    This function produces a tuple representing the start and end offsets
    (in seconds) relative to the current time. It is typically used to
    specify the time range when querying metrics from the Sysdig API.

    Args:
        last_seconds (int, optional): Duration of the window in seconds.
            Defaults to 600 (10 minutes).

    Returns:
        Tuple[int, int]: A pair (start, end), where start is the negative
        offset (e.g., -600) and end is 0, indicating "now".
    
    Example:
        >>> build_time_window(300)
        (-300, 0)
    """
    # Return negative start offset and 0 for "now"
    return (-int(last_seconds), 0)


def print_table(res: dict, metric_defs: List[dict], sampling: int, scope: str) -> None:
    """
    Display Sysdig metric results in a tabular format.

    Prints the collected metric values aligned under headers for easier
    inspection during monitoring and debugging. If sampling is enabled,
    each row is associated with a timestamp.

    Args:
        res (dict): Sysdig response containing "start", "end", and "data" fields.
        metric_defs (List[dict]): Metric definitions with "id" keys describing metrics.
        sampling (int): Sampling interval in seconds. If >0, timestamps are included.
        scope (str): Optional filter scope (e.g., Kubernetes namespace) for context.

    Returns:
        None. The function prints the formatted table to stdout.
    
    Example:
        >>> print_table(response, [{"id": "cpu.used.percent"}], 60, "acmeair")
    """
    col_len = 25  # Fixed column width for alignment
    start, end, data = res["start"], res["end"], res["data"]

    # Print header with scope and time range
    print(f"Data for {scope if scope else 'everything'} from {start} to {end}\n")

    # Build header row from metric IDs (truncate if too long)
    headers = ' '.join(
        [(m["id"] if len(m["id"]) < col_len else m["id"][:col_len-3] + '...').ljust(col_len)
         for m in metric_defs]
    )

    # Add timestamp column if sampling interval is set
    print(f"{'timestamp'.ljust(col_len)} {headers}" if sampling > 0 else headers)
    print('')

    # Print each row of metric data
    for row in data:
        ts = row["t"] if sampling > 0 else start
        vals = row["d"]

        # Format each value with truncation if too long
        body = ' '.join(
            [(str(v) if len(str(v)) < col_len else str(v)[:col_len-3] + '...').ljust(col_len)
             for v in vals]
        )

        # Include timestamp column if sampling enabled
        print(f"{('<t: %d>' % ts).ljust(col_len)} {body}" if sampling > 0 else body)


def plot_all_metrics(all_res: dict, metric_defs: List[dict], sampling: int,
                     title_prefix: str = "", outdir: str = "charts") -> None:
    """
    Generate and save line plots for both Sysdig and derived metrics.

    For each metric definition, this function extracts its values over time
    from the Sysdig response, creates a time-series plot, and saves it as a PNG file.
    Derived metrics (error rates, cost per request, etc.) are also computed
    and plotted alongside raw metrics.

    Args:
        res (dict): Sysdig response containing "data", "start", and optionally "end".
        metric_defs (List[dict]): Metric definitions with "id" keys.
        sampling (int): Sampling interval in seconds. Determines whether to use timestamps.
        title_prefix (str, optional): Text prefix for chart titles and filenames.
        outdir (str, optional): Output directory to store charts. Defaults to "charts".
        service (str, optional): Service name label for titles. Defaults to "service".
    """
    os.makedirs(outdir, exist_ok=True)
    ids = [m["id"] for m in metric_defs]

    all_metrics = {}


    for service, res in all_res.items():
        if not res.get("data"):
            print(f"No data points for {service}, skipping plots.")
            continue

        
        timestamps = [row["t"] for row in res["data"]] if sampling > 0 else [res["start"]] * len(res["data"])
        ts_readable = [datetime.datetime.fromtimestamp(t) for t in timestamps]

    # --- Raw metric plots ---
    # for idx, mid in enumerate(ids):
    #     values = [row["d"][idx] for row in res["data"] if row["d"][idx] is not None]
    #     if not values:
    #         continue
    #     plt.figure(figsize=(8, 3))
    #     plt.plot(ts_readable[:len(values)], values, marker="o", linestyle="-", label=mid)
    #     plt.xlabel("Time")
    #     plt.ylabel("Value")
    #     plt.title(f"{title_prefix} {mid} ({service})")
    #     plt.legend()
    #     plt.grid(True, linestyle="--", alpha=0.6)
    #     plt.tight_layout()
    #     safe_metric = mid.replace(".", "_").replace("/", "_")
    #     filename = os.path.join(outdir, f"{title_prefix}_{safe_metric}.png")
    #     plt.savefig(filename, dpi=150)
    #     plt.close()

    # --- Derived metric plots ---
    # for row in res["data"]:
    #     raw_dict = dict(zip(ids, row["d"]))
    #     derived = evaluate_derived_metrics(raw_dict)
    #     break  # just to get keys for plotting structure

        derived_series = {mid: [] for mid in DERIVED_METRICS}
        for row in res["data"]:
            raw_dict = dict(zip(ids, row["d"]))
            derived = evaluate_derived_metrics(raw_dict)
            for k, v in derived.items():
                derived_series[k].append(v)

        for mid, values in derived_series.items():
            if not values or all(v is None for v in values):
                continue
            all_metrics.setdefault(mid, {})[service] = (ts_readable[:len(values)], values)

    for mid, service_data in all_metrics.items():
        plt.figure(figsize=(8, 8))
        for svc, (ts_readable, values) in service_data.items():
            plt.plot(ts_readable[:len(values)], values, marker="o", linestyle="-", label=svc)

        plt.xlabel("Time")
        plt.ylabel("Value")
        plt.title(f"{title_prefix} {mid} (All Services)")
        plt.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.15),  
            ncol=len(service_data),
            frameon=False
        )

        plt.gcf().autofmt_xdate()
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())

        plt.grid(True, linestyle="--", alpha=0.6)
        # plt.tight_layout(rect=[0, 0.05, 1, 1])
        safe_metric = mid.replace(".", "_")
        filename = os.path.join(outdir, f"{title_prefix}_{safe_metric}.png")
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()

    plot_metric_combined(all_metrics, title_prefix, outdir)

def plot_metric_combined(all_metrics: dict, title_prefix: str = "", outdir: str = "charts") -> None:
    """
    Generate and save combined line plots for all metrics across services.

    This function aggregates metric values from multiple services and
    creates a single plot per metric, showing how each service's metric
    values change over time. Each service is represented by a distinct line
    in the plot.

    Args:
        all_res (dict): Mapping of service name to Sysdig response dicts.
        title_prefix (str, optional): Text prefix for chart titles and filenames.
        outdir (str, optional): Output directory to store charts. Defaults to "charts".
    """
    os.makedirs(outdir, exist_ok=True)
    metric_names = list(all_metrics.keys())
    num_metrics = len(metric_names)

    if num_metrics == 0:
        print("No metrics found to plot.")
        return

    col = 2
    row = (num_metrics + 1) // col

    fig, axes = plt.subplots(row, col, figsize=(14,8))
    axes = axes.flatten()
    all_services = set()

    title = ["Error Rate", "Latency (ms)", "Throughput (req/s)", "Cost per Request"]

    for i, mid in enumerate(metric_names):
        ax = axes[i]
        service_data = all_metrics[mid]
        for svc, (ts_readable, values) in service_data.items():
            ax.plot(ts_readable, values, marker="o", linestyle="-", label=svc)
            all_services.add(svc)

        ax.set_title(title[i], fontsize=11, fontweight='bold')
        ax.set_ylabel(mid, fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))

        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment("right")

    for ax in axes[num_metrics:]:
        ax.axis("off")

    fig.text(0.5, 0.04, "Time", ha="center", fontsize=12)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.05),
        ncol=len(all_services),
        frameon=False,
        fontsize=9
    )

    fig.suptitle(f"Derived Metrics", fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0.08, 1, 0.95])

    filename = os.path.join(outdir, f"combined_plot.png")
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close(fig)

def evaluate_derived_metrics(raw_row: dict) -> dict:
    """
    Compute derived metrics (error rates, cost per request, etc.)
    based on raw metric values in one data row.

    Args:
        raw_row (dict): Mapping of metric_id -> value from Sysdig response.

    Returns:
        dict: Mapping of derived_metric_id -> computed value.
    """
    derived = {}
    for mid, fn in DERIVED_METRICS.items():
        try:
            derived[mid] = fn(raw_row)
        except Exception:
            derived[mid] = None
    return derived