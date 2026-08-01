"""
Reflect Agent - AWARE Framework

This agent observes post-adaptation performance to verify effectiveness,
identifying both improvements and unintended consequences.

Responsibilities:
- Monitor system state after adaptations
- Compare pre/post-adaptation metrics
- Evaluate adaptation success
- Detect unintended side effects
"""

import datetime
from typing import Dict, List, Optional

from constants import REFLECTION_WINDOW, SUCCESS_THRESHOLD, DEGRADATION_THRESHOLD


class ReflectAgent:
    """
    The Reflect Agent evaluates adaptation outcomes.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the Reflect Agent.
        
        Args:
            logger: Optional logger for agent activities
        """
        self.logger = logger
        self.reflection_history = []
    
    def reflect(self, pre_state: Dict, post_state: Dict, 
                decision: Dict, execution_result: Dict) -> Dict:
        """
        Analyze the outcome of an adaptation.
        
        Args:
            pre_state: System state before adaptation (from Assess)
            post_state: System state after adaptation (from Assess)
            decision: Decision that was made (from Weigh)
            execution_result: Result of execution (from Act)
            
        Returns:
            Dictionary containing:
            - success: Whether adaptation was successful
            - improvements: Metrics that improved
            - degradations: Metrics that degraded
            - side_effects: Unintended consequences
            - recommendations: Suggestions for future adaptations
        """
        self.log("[REFLECT] Analyzing adaptation outcome")
        
        # Check if execution itself succeeded
        if not execution_result.get("success", False):
            reflection = {
                "timestamp": datetime.datetime.now().isoformat(),
                "success": False,
                "reason": "Execution failed",
                "errors": execution_result.get("errors", []),
                "recommendations": ["Review execution errors", "Check system permissions"]
            }
            self.reflection_history.append(reflection)
            return reflection
        
        # Compare metrics
        improvements = self._identify_improvements(pre_state, post_state)
        degradations = self._identify_degradations(pre_state, post_state)
        
        # Analyze health score change
        pre_health = pre_state.get("health_score", 100)
        post_health = post_state.get("health_score", 100)
        health_delta = post_health - pre_health
        
        # Determine overall success
        success = self._evaluate_success(health_delta, improvements, degradations)
        
        # Identify side effects
        side_effects = self._detect_side_effects(
            pre_state, post_state, decision.get("actions", [])
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            success, improvements, degradations, side_effects
        )
        
        reflection = {
            "timestamp": datetime.datetime.now().isoformat(),
            "success": success,
            "health_delta": health_delta,
            "pre_health": pre_health,
            "post_health": post_health,
            "improvements": improvements,
            "degradations": degradations,
            "side_effects": side_effects,
            "recommendations": recommendations,
            "actions_taken": [a.get("name") for a in decision.get("actions", [])]
        }
        
        self.reflection_history.append(reflection)
        
        self.log(f"[REFLECT] Reflection complete: "
                f"{'SUCCESS' if success else 'NEEDS IMPROVEMENT'} "
                f"(health Δ: {health_delta:+.1f})")
        
        return reflection
    
    def _identify_improvements(self, pre_state: Dict, post_state: Dict) -> List[Dict]:
        """
        Identify metrics that improved after adaptation.
        
        Args:
            pre_state: State before adaptation
            post_state: State after adaptation
            
        Returns:
            List of improvement dictionaries
        """
        improvements = []
        
        pre_metrics = pre_state.get("derived_metrics", {})
        post_metrics = post_state.get("derived_metrics", {})
        
        for metric, post_value in post_metrics.items():
            if metric not in pre_metrics:
                continue
            
            pre_value = pre_metrics[metric]
            
            # Skip None values
            if pre_value is None or post_value is None:
                continue
            
            # Calculate percentage change
            if pre_value != 0:
                pct_change = ((post_value - pre_value) / abs(pre_value)) * 100
            else:
                pct_change = 0
            
            # Determine if improvement (depends on metric type)
            is_improvement = False
            
            # For error rates and latency, lower is better
            if metric in ["http.error.rate", "http.latency", "cost.per.request"]:
                if post_value < pre_value:
                    is_improvement = True
            # For throughput, higher is better
            elif metric in ["http.throughput"]:
                if post_value > pre_value:
                    is_improvement = True
            
            if is_improvement and abs(pct_change) > 5:  # Significant change threshold
                improvements.append({
                    "metric": metric,
                    "pre_value": pre_value,
                    "post_value": post_value,
                    "change_pct": pct_change
                })
        
        return improvements
    
    def _identify_degradations(self, pre_state: Dict, post_state: Dict) -> List[Dict]:
        """
        Identify metrics that degraded after adaptation.
        
        Args:
            pre_state: State before adaptation
            post_state: State after adaptation
            
        Returns:
            List of degradation dictionaries
        """
        degradations = []
        
        pre_metrics = pre_state.get("derived_metrics", {})
        post_metrics = post_state.get("derived_metrics", {})
        
        for metric, post_value in post_metrics.items():
            if metric not in pre_metrics:
                continue
            
            pre_value = pre_metrics[metric]
            
            if pre_value is None or post_value is None:
                continue
            
            if pre_value != 0:
                pct_change = ((post_value - pre_value) / abs(pre_value)) * 100
            else:
                pct_change = 0
            
            # Determine if degradation
            is_degradation = False
            
            # For error rates and latency, higher is worse
            if metric in ["http.error.rate", "http.latency", "cost.per.request"]:
                if post_value > pre_value:
                    is_degradation = True
            # For throughput, lower is worse
            elif metric in ["http.throughput"]:
                if post_value < pre_value:
                    is_degradation = True
            
            if is_degradation and abs(pct_change) > 5:
                degradations.append({
                    "metric": metric,
                    "pre_value": pre_value,
                    "post_value": post_value,
                    "change_pct": pct_change
                })
        
        return degradations
    
    def _evaluate_success(self, health_delta: float, 
                         improvements: List[Dict], 
                         degradations: List[Dict]) -> bool:
        """
        Determine if adaptation was successful overall.
        
        Args:
            health_delta: Change in health score
            improvements: List of improved metrics
            degradations: List of degraded metrics
            
        Returns:
            True if successful, False otherwise
        """
        # Success if health improved significantly
        if health_delta > SUCCESS_THRESHOLD * 100:
            return True
        
        # Failure if health degraded significantly
        if health_delta < DEGRADATION_THRESHOLD * 100:
            return False
        
        # Otherwise, compare improvements vs degradations
        if len(improvements) > len(degradations):
            return True
        
        # If tied, check magnitude of changes
        if improvements and degradations:
            avg_improvement = sum(abs(i["change_pct"]) for i in improvements) / len(improvements)
            avg_degradation = sum(abs(d["change_pct"]) for d in degradations) / len(degradations)
            return avg_improvement > avg_degradation
        
        # If only improvements, success
        if improvements:
            return True
        
        # Otherwise, no clear improvement
        return False
    
    def _detect_side_effects(self, pre_state: Dict, post_state: Dict, 
                            actions: List[Dict]) -> List[str]:
        """
        Detect unintended consequences of adaptations.
        
        Args:
            pre_state: State before adaptation
            post_state: State after adaptation
            actions: Actions that were taken
            
        Returns:
            List of side effect descriptions
        """
        side_effects = []
        
        # Check for new SLO violations
        pre_violations = set(v["metric"] for v in pre_state.get("slo_violations", []))
        post_violations = set(v["metric"] for v in post_state.get("slo_violations", []))
        new_violations = post_violations - pre_violations
        
        if new_violations:
            side_effects.append(
                f"New SLO violations introduced: {', '.join(new_violations)}"
            )
        
        # Check for new anomalies
        pre_anomalies = set(pre_state.get("anomalies", {}).keys())
        post_anomalies = set(post_state.get("anomalies", {}).keys())
        new_anomalies = post_anomalies - pre_anomalies
        
        if new_anomalies:
            side_effects.append(
                f"New anomalies detected: {', '.join(new_anomalies)}"
            )
        
        # Check if scaling action caused resource exhaustion
        for action in actions:
            if action.get("name") == "horizontal" and action.get("operation") == "increase":
                # Check if cost metrics spiked
                pre_cost = pre_state.get("derived_metrics", {}).get("cost.per.request", 0)
                post_cost = post_state.get("derived_metrics", {}).get("cost.per.request", 0)
                
                if post_cost > pre_cost * 1.5:
                    side_effects.append(
                        f"Cost per request increased significantly after scaling up"
                    )
        
        return side_effects
    
    def _generate_recommendations(self, success: bool, improvements: List[Dict],
                                 degradations: List[Dict], 
                                 side_effects: List[str]) -> List[str]:
        """
        Generate recommendations for future adaptations.
        
        Args:
            success: Whether adaptation was successful
            improvements: List of improvements
            degradations: List of degradations
            side_effects: List of side effects
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if success:
            recommendations.append("Adaptation was successful - consider similar actions for similar conditions")
            
            if improvements:
                top_improvement = max(improvements, key=lambda x: abs(x["change_pct"]))
                recommendations.append(
                    f"Best improvement: {top_improvement['metric']} "
                    f"({top_improvement['change_pct']:+.1f}%)"
                )
        else:
            recommendations.append("Adaptation did not achieve desired outcome - consider alternative strategies")
            
            if degradations:
                worst_degradation = max(degradations, key=lambda x: abs(x["change_pct"]))
                recommendations.append(
                    f"Address degradation in {worst_degradation['metric']} "
                    f"({worst_degradation['change_pct']:+.1f}%)"
                )
        
        if side_effects:
            recommendations.append("Monitor side effects and consider corrective actions")
            recommendations.extend(side_effects)
        
        if not improvements and not degradations:
            recommendations.append("No significant metric changes observed - may need longer observation window")
        
        return recommendations
    
    def get_reflection_summary(self, lookback: int = None) -> Dict:
        """
        Get summary statistics of recent reflections.
        
        Args:
            lookback: Number of recent reflections to analyze (None = all)
            
        Returns:
            Summary dictionary
        """
        if lookback is None:
            history = self.reflection_history
        else:
            history = self.reflection_history[-lookback:]
        
        if not history:
            return {"total": 0}
        
        successful = sum(1 for r in history if r.get("success", False))
        
        avg_health_delta = sum(r.get("health_delta", 0) for r in history) / len(history)
        
        return {
            "total_reflections": len(history),
            "successful": successful,
            "failed": len(history) - successful,
            "success_rate": successful / len(history) if history else 0,
            "avg_health_delta": avg_health_delta
        }
    
    def log(self, message: str):
        """Log a message."""
        if self.logger:
            self.logger(message)
        else:
            print(message)
