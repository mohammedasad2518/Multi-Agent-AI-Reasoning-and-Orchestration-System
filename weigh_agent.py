"""
Weigh Agent - AWARE Framework

This agent serves as the cognitive core of the framework. It uses symbolic reasoning 
and utility-based optimization to evaluate adaptation strategies against defined 
service-level goals.

Responsibilities:
- Analyze system snapshots from Assess Agent
- Evaluate potential adaptation strategies
- Select optimal actions using utility functions
- Apply rule-based reasoning for decision-making
"""

from typing import List, Dict, Optional, Tuple
import datetime

from constants import *


class WeighAgent:
    """
    The Weigh Agent performs cognitive analysis and strategic planning.
    """
    
    def __init__(self, knowledge_base=None, logger=None):
        """
        Initialize the Weigh Agent.
        
        Args:
            knowledge_base: Shared knowledge base for learned policies
            logger: Optional logger for agent activities
        """
        self.knowledge_base = knowledge_base
        self.logger = logger
        self.decision_history = []
        
    def weigh(self, system_snapshot: Dict, service: str) -> Dict:
        """
        Analyze system state and generate adaptation plan.
        
        Args:
            system_snapshot: System state from Assess Agent
            service: Service name
            
        Returns:
            Dictionary containing:
            - actions: List of recommended actions
            - rationale: Explanation for decisions
            - utility_scores: Utility scores for considered options
            - confidence: Confidence level in recommendations
        """
        self.log(f"[WEIGH] Analyzing system snapshot for {service}")
        
        # Extract relevant metrics
        derived_metrics = system_snapshot.get("derived_metrics", {})
        slo_violations = system_snapshot.get("slo_violations", [])
        anomalies = system_snapshot.get("anomalies", {})
        health_score = system_snapshot.get("health_score", 100)
        
        # Generate candidate actions
        candidates = self._generate_candidates(derived_metrics, slo_violations, 
                                               anomalies, service)
        
        # Evaluate utilities for each candidate
        evaluated_candidates = self._evaluate_utilities(candidates, derived_metrics, 
                                                        health_score)
        
        # Select best action(s) based on utility
        selected_actions = self._select_actions(evaluated_candidates)
        
        # Build decision package
        decision = {
            "timestamp": datetime.datetime.now().isoformat(),
            "service": service,
            "actions": selected_actions,
            "rationale": self._build_rationale(selected_actions, system_snapshot),
            "candidates_evaluated": len(candidates),
            "confidence": self._compute_confidence(selected_actions, health_score),
            "utility_scores": {a["name"]: a.get("utility", 0) 
                              for a in evaluated_candidates}
        }
        
        # Store decision in history
        self.decision_history.append(decision)
        
        self.log(f"[WEIGH] Generated {len(selected_actions)} actions with "
                f"confidence {decision['confidence']:.2f}")
        
        return decision
    
    def _generate_candidates(self, derived_metrics: Dict, slo_violations: List,
                            anomalies: Dict, service: str) -> List[Dict]:
        """
        Generate candidate adaptation actions based on system state.
        
        Args:
            derived_metrics: Computed derived metrics
            slo_violations: List of SLO violations
            anomalies: Detected anomalies
            service: Service name
            
        Returns:
            List of candidate action dictionaries
        """
        candidates = []
        
        # Extract key metrics
        error_rate = derived_metrics.get("http.error.rate", 0)
        latency = derived_metrics.get("http.latency", 0)
        throughput = derived_metrics.get("http.throughput", 0)
        cost_per_request = derived_metrics.get("cost.per.request", 0)
        
        # Get thresholds
        max_error_rate = THRESHOLDS.get("http.error.rate", 0.05)
        max_latency = THRESHOLDS.get("http.latency", 1000)
        min_throughput = THRESHOLDS.get("http.throughput", 10)
        max_cost_per_request = THRESHOLDS.get("cost.per.request", 0.001)
        
        # Rule 1: High error rate or latency → scale horizontally
        if error_rate > max_error_rate or latency > max_latency:
            candidates.append({
                "name": "horizontal",
                "service": service,
                "operation": "increase",
                "amount": 1,
                "reason": f"High error rate ({error_rate:.2%}) or latency ({latency:.0f}ms)",
                "priority": 1  # High priority
            })
        
        # Rule 2: Low load and acceptable performance → scale down
        elif (error_rate < max_error_rate * 0.25 and 
              latency < max_latency * 0.5 and 
              throughput < min_throughput):
            candidates.append({
                "name": "horizontal",
                "service": service,
                "operation": "decrease",
                "amount": 1,
                "reason": f"Low load: error rate {error_rate:.2%}, latency {latency:.0f}ms",
                "priority": 3  # Lower priority
            })
        
        # Rule 3: High cost per request → optimize resources (vertical scaling)
        if cost_per_request > max_cost_per_request * 1.05:
            candidates.append({
                "name": "vertical",
                "service": service,
                "operation": "increase",
                "resource": "cpu/mem",
                "factor": 1.5,
                "reason": f"High cost per request: ${cost_per_request:.4f}",
                "priority": 2  # Medium priority
            })
        
        # Rule 4: Very low cost per request → reduce resource allocation
        elif cost_per_request < max_cost_per_request * 0.5:
            candidates.append({
                "name": "vertical",
                "service": service,
                "operation": "decrease",
                "resource": "cpu/mem",
                "factor": 0.75,
                "reason": f"Low resource utilization: ${cost_per_request:.4f} per request",
                "priority": 3  # Lower priority
            })
        
        # Rule 5: Critical SLO violations → emergency scale-up
        critical_violations = [v for v in slo_violations if v.get("severity", 4) <= 2]
        if critical_violations:
            candidates.append({
                "name": "horizontal",
                "service": service,
                "operation": "increase",
                "amount": 2,  # More aggressive scaling
                "reason": f"Critical SLO violations: {len(critical_violations)} detected",
                "priority": 0  # Highest priority
            })
        
        # Rule 6: Anomalies detected → investigate and potentially restart
        if len(anomalies) > 5:
            candidates.append({
                "name": "restart",
                "service": service,
                "reason": f"Multiple anomalies detected: {len(anomalies)} metrics affected",
                "priority": 2
            })
        
        return candidates
    
    def _evaluate_utilities(self, candidates: List[Dict], derived_metrics: Dict,
                           health_score: float) -> List[Dict]:
        """
        Evaluate utility score for each candidate action.
        
        Args:
            candidates: List of candidate actions
            derived_metrics: Current derived metrics
            health_score: Current health score
            
        Returns:
            List of candidates with utility scores added
        """
        for candidate in candidates:
            # Base utility from priority (higher priority = higher base utility)
            priority = candidate.get("priority", 3)
            base_utility = 100 - (priority * 20)  # 0->100, 1->80, 2->60, 3->40
            
            # Adjust utility based on action type and current state
            if candidate["name"] == "horizontal":
                if candidate["operation"] == "increase":
                    # Increasing replicas is more valuable when health is low
                    utility = base_utility * (1 - health_score / 100)
                else:
                    # Decreasing replicas is more valuable when health is high
                    utility = base_utility * (health_score / 100)
            
            elif candidate["name"] == "vertical":
                # Vertical scaling utility based on cost considerations
                cost_per_request = derived_metrics.get("cost.per.request", 0)
                max_cost = THRESHOLDS.get("cost.per.request", 0.001)
                
                if candidate["operation"] == "increase":
                    # More valuable when cost is very high
                    utility = base_utility * min(cost_per_request / max_cost, 2.0)
                else:
                    # More valuable when cost is very low
                    utility = base_utility * max(1 - cost_per_request / max_cost, 0.5)
            
            elif candidate["name"] == "restart":
                # Restart utility based on health degradation
                utility = base_utility * (1 - health_score / 100)
            
            else:
                utility = base_utility
            
            candidate["utility"] = utility
        
        return candidates
    
    def _select_actions(self, evaluated_candidates: List[Dict]) -> List[Dict]:
        """
        Select best action(s) from evaluated candidates.
        
        Args:
            evaluated_candidates: Candidates with utility scores
            
        Returns:
            List of selected actions to execute
        """
        if not evaluated_candidates:
            return []
        
        # Sort by utility (descending)
        sorted_candidates = sorted(evaluated_candidates, 
                                  key=lambda x: x.get("utility", 0), 
                                  reverse=True)
        
        # Select top action(s)
        # For now, select the single best action
        # Could be extended to select multiple compatible actions
        selected = [sorted_candidates[0]] if sorted_candidates else []
        
        # Query knowledge base for learned preferences (if available)
        if self.knowledge_base:
            selected = self._apply_learned_policies(selected, sorted_candidates)
        
        return selected
    
    def _apply_learned_policies(self, selected: List[Dict], 
                                candidates: List[Dict]) -> List[Dict]:
        """
        Apply learned policies from knowledge base to refine selection.
        
        Args:
            selected: Currently selected actions
            candidates: All evaluated candidates
            
        Returns:
            Refined action selection
        """
        # Placeholder for RL-based policy refinement
        # This will be implemented with the Enrich Agent's learning
        return selected
    
    def _build_rationale(self, actions: List[Dict], 
                        system_snapshot: Dict) -> str:
        """
        Build human-readable rationale for decisions.
        
        Args:
            actions: Selected actions
            system_snapshot: Current system state
            
        Returns:
            Rationale string
        """
        if not actions:
            return "No actions needed - system operating within normal parameters"
        
        rationale_parts = []
        health = system_snapshot.get("health_score", 100)
        violations = len(system_snapshot.get("slo_violations", []))
        anomalies = len(system_snapshot.get("anomalies", {}))
        
        rationale_parts.append(f"System health: {health:.1f}/100")
        
        if violations > 0:
            rationale_parts.append(f"{violations} SLO violations detected")
        
        if anomalies > 0:
            rationale_parts.append(f"{anomalies} metric anomalies detected")
        
        for action in actions:
            rationale_parts.append(f"Action: {action['name']} - {action.get('reason', 'N/A')}")
        
        return "; ".join(rationale_parts)
    
    def _compute_confidence(self, actions: List[Dict], health_score: float) -> float:
        """
        Compute confidence level in recommendations.
        
        Args:
            actions: Selected actions
            health_score: Current health score
            
        Returns:
            Confidence score (0-1)
        """
        if not actions:
            # High confidence when no action is needed and health is good
            return 0.9 if health_score > 80 else 0.5
        
        # Confidence based on utility score of selected action
        max_utility = max(a.get("utility", 0) for a in actions)
        
        # Normalize to 0-1 range
        confidence = min(max_utility / 100, 1.0)
        
        return confidence
    
    def get_decision_history(self, lookback: int = 10) -> List[Dict]:
        """
        Retrieve recent decision history.
        
        Args:
            lookback: Number of past decisions to retrieve
            
        Returns:
            List of decision dictionaries
        """
        return self.decision_history[-lookback:]
    
    def log(self, message: str):
        """Log a message."""
        if self.logger:
            self.logger(message)
        else:
            print(message)
