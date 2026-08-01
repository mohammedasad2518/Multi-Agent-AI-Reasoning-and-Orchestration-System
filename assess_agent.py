"""
Assess Agent - AWARE Framework

This agent continuously monitors resource usage, latency and fault signals through 
Sysdig metrics and provides contextual system snapshots to the decision layer.

Responsibilities:
- Collect telemetry data from Sysdig
- Detect anomalies using Isolation Forest
- Provide enriched system state snapshots
- Monitor SLO compliance
"""

import datetime
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest

from constants import *
from utils import build_time_window


class AssessAgent:
    """
    The Assess Agent monitors system state and detects anomalies.
    """
    
    def __init__(self, client, logger=None):
        """
        Initialize the Assess Agent.
        
        Args:
            client: Sysdig client for metric collection
            logger: Optional logger for agent activities
        """
        self.client = client
        self.logger = logger
        self.anomaly_history = {}
        self.metric_history = {}
        
    def assess(self, metrics: List[dict], service: str, 
               scope: Optional[str] = None) -> Dict:
        """
        Perform comprehensive assessment of system state.
        
        Args:
            metrics: List of metric definitions to monitor
            service: Service name being assessed
            scope: Optional Sysdig scope filter
            
        Returns:
            Dictionary containing:
            - raw_metrics: Raw metric data from Sysdig
            - derived_metrics: Computed derived metrics
            - anomalies: Detected anomalies
            - slo_violations: SLO threshold breaches
            - system_snapshot: Contextual system state
        """
        self.log(f"[ASSESS] Starting assessment for {service}")
        
        # Collect telemetry data
        raw_data = self._collect_telemetry(metrics, scope)
        
        if not raw_data:
            self.log("[ASSESS] No data collected, skipping assessment")
            return None
            
        # Extract latest values and compute derived metrics
        raw_metrics = self._extract_latest_values(raw_data, metrics)
        derived_metrics = self._compute_derived_metrics(raw_metrics)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(raw_data, metrics)
        
        # Check SLO violations
        slo_violations = self._check_slo_violations(raw_metrics, derived_metrics)
        
        # Build comprehensive system snapshot
        system_snapshot = {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": service,
            "raw_metrics": raw_metrics,
            "derived_metrics": derived_metrics,
            "anomalies": anomalies,
            "slo_violations": slo_violations,
            "health_score": self._compute_health_score(slo_violations, anomalies)
        }
        
        # Store in history
        self._update_history(service, system_snapshot)
        
        self.log(f"[ASSESS] Assessment complete: {len(anomalies)} anomalies, "
                f"{len(slo_violations)} SLO violations")
        
        return system_snapshot
    
    def _collect_telemetry(self, metrics: List[dict], 
                          scope: Optional[str] = None) -> Optional[dict]:
        """
        Collect telemetry data from Sysdig.
        
        Args:
            metrics: Metric definitions to collect
            scope: Optional filter scope
            
        Returns:
            Sysdig response data or None if collection fails
        """
        start, end = build_time_window(BASELINE_MINUTES * 60)
        ok, res = self.client.get_data(metrics, start, end, BASELINE_STEP, filter=scope)
        
        if not ok:
            self.log(f"[ASSESS] Failed to collect telemetry: {res}")
            return None
            
        return res
    
    def _extract_latest_values(self, raw_data: dict, 
                               metric_defs: List[dict]) -> Dict[str, float]:
        """
        Extract the latest value for each metric from raw Sysdig data.
        
        Args:
            raw_data: Sysdig response with time series data
            metric_defs: Metric definitions
            
        Returns:
            Dictionary mapping metric_id to latest value
        """
        latest_values = {}
        ids = [m["id"] for m in metric_defs]
        
        for idx, mid in enumerate(ids):
            # Extract non-null values for this metric
            series = [row["d"][idx] for row in raw_data["data"] 
                     if row["d"][idx] is not None]
            
            if series:
                latest_values[mid] = series[-1]
        
        return latest_values
    
    def _compute_derived_metrics(self, raw_metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Compute derived metrics from raw metric values.
        
        Args:
            raw_metrics: Dictionary of raw metric values
            
        Returns:
            Dictionary of derived metric values
        """
        derived = {}
        
        for mid, fn in DERIVED_METRICS.items():
            try:
                derived[mid] = fn(raw_metrics)
            except Exception as e:
                self.log(f"[ASSESS] Error computing {mid}: {e}")
                derived[mid] = None
                
        return derived
    
    def _detect_anomalies(self, raw_data: dict, 
                         metric_defs: List[dict]) -> Dict[str, List[int]]:
        """
        Detect anomalies in metric time series using Isolation Forest.
        
        Args:
            raw_data: Sysdig response with time series data
            metric_defs: Metric definitions
            
        Returns:
            Dictionary mapping metric_id to list of anomalous indices
        """
        anomalies = {}
        ids = [m["id"] for m in metric_defs]
        
        for idx, mid in enumerate(ids):
            # Extract time series values
            series = [row["d"][idx] for row in raw_data["data"] 
                     if row["d"][idx] is not None]
            
            if len(series) < 10:
                continue
                
            # Detect anomalies using Isolation Forest
            vals = np.array(series).reshape(-1, 1)
            model = IsolationForest(contamination=0.05, random_state=42)
            preds = model.fit_predict(vals)
            
            anomaly_indices = [i for i, p in enumerate(preds) if p == -1]
            
            if anomaly_indices:
                anomalies[mid] = anomaly_indices
                
        return anomalies
    
    def _check_slo_violations(self, raw_metrics: Dict[str, float], 
                             derived_metrics: Dict[str, float]) -> List[Dict]:
        """
        Check for SLO threshold violations.
        
        Args:
            raw_metrics: Raw metric values
            derived_metrics: Derived metric values
            
        Returns:
            List of violation dictionaries
        """
        violations = []
        all_metrics = {**raw_metrics, **derived_metrics}
        
        for metric_id, (direction, threshold) in SLO_THRESHOLDS.items():
            if metric_id not in all_metrics:
                continue
                
            value = all_metrics[metric_id]
            
            if direction == "gt" and value > threshold:
                violations.append({
                    "metric": metric_id,
                    "value": value,
                    "threshold": threshold,
                    "direction": direction,
                    "severity": METRIC_SEVERITY.get(metric_id, 4)
                })
            elif direction == "lt" and value < threshold:
                violations.append({
                    "metric": metric_id,
                    "value": value,
                    "threshold": threshold,
                    "direction": direction,
                    "severity": METRIC_SEVERITY.get(metric_id, 4)
                })
                
        return violations
    
    def _compute_health_score(self, slo_violations: List[Dict], 
                             anomalies: Dict) -> float:
        """
        Compute overall health score (0-100) based on violations and anomalies.
        
        Args:
            slo_violations: List of SLO violations
            anomalies: Dictionary of detected anomalies
            
        Returns:
            Health score from 0 (critical) to 100 (healthy)
        """
        base_score = 100.0
        
        # Penalize for SLO violations (weighted by severity)
        for violation in slo_violations:
            severity = violation.get("severity", 4)
            penalty = 10 / severity  # Higher severity = bigger penalty
            base_score -= penalty
            
        # Penalize for anomalies
        total_anomalies = sum(len(indices) for indices in anomalies.values())
        base_score -= total_anomalies * 0.5
        
        return max(base_score, 0.0)
    
    def _update_history(self, service: str, snapshot: Dict):
        """
        Update historical record of assessments.
        
        Args:
            service: Service name
            snapshot: Assessment snapshot
        """
        if service not in self.metric_history:
            self.metric_history[service] = []
            
        self.metric_history[service].append(snapshot)
        
        # Keep only recent history (last 100 snapshots)
        if len(self.metric_history[service]) > 100:
            self.metric_history[service] = self.metric_history[service][-100:]
    
    def get_history(self, service: str, lookback: int = 10) -> List[Dict]:
        """
        Retrieve historical assessments for a service.
        
        Args:
            service: Service name
            lookback: Number of past assessments to retrieve
            
        Returns:
            List of historical snapshots
        """
        if service not in self.metric_history:
            return []
            
        return self.metric_history[service][-lookback:]
    
    def log(self, message: str):
        """Log a message."""
        if self.logger:
            self.logger(message)
        else:
            print(message)
