"""
Enrich Agent - AWARE Framework

This agent learns from Reflect outcomes using reinforcement learning and pattern mining,
updating rules and models in the shared knowledge base. Over time, the system 
self-optimizes for new conditions.

Responsibilities:
- Learn from adaptation outcomes
- Update decision policies
- Mine patterns in successful/failed adaptations
- Maintain and evolve knowledge base
"""

import datetime
import json
import pickle
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from constants import (
    RL_ENABLED, RL_EXPLORATION_RATE, RL_LEARNING_EPISODES, RL_UPDATE_FREQUENCY,
    PATTERN_MINING_MIN_SUPPORT, PATTERN_MINING_MIN_CONFIDENCE,
    KNOWLEDGE_BASE_PATH
)


class EnrichAgent:
    """
    The Enrich Agent learns from outcomes and updates the knowledge base.
    """
    
    def __init__(self, knowledge_base_path=KNOWLEDGE_BASE_PATH, logger=None):
        """
        Initialize the Enrich Agent.
        
        Args:
            knowledge_base_path: Path to persistent knowledge base file
            logger: Optional logger for agent activities
        """
        self.logger = logger
        self.knowledge_base_path = knowledge_base_path
        self.knowledge_base = self._load_knowledge_base()
        self.learning_cycles = 0
        
        # Pattern mining structures
        self.pattern_counts = defaultdict(int)
        self.pattern_successes = defaultdict(int)
        
        # RL structures (simple Q-learning)
        self.q_table = {}  # State-action values
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.epsilon = RL_EXPLORATION_RATE
        
    def enrich(self, reflection: Dict, decision: Dict, 
               pre_state: Dict, post_state: Dict) -> Dict:
        """
        Learn from an adaptation cycle and update knowledge base.
        
        Args:
            reflection: Reflection analysis from Reflect Agent
            decision: Decision made by Weigh Agent
            pre_state: System state before adaptation
            post_state: System state after adaptation
            
        Returns:
            Dictionary containing:
            - patterns_learned: New patterns discovered
            - policies_updated: Policies that were updated
            - knowledge_base_size: Current size of knowledge base
        """
        self.log("[ENRICH] Learning from adaptation cycle")
        
        self.learning_cycles += 1
        
        # Extract key information
        success = reflection.get("success", False)
        actions = decision.get("actions", [])
        health_delta = reflection.get("health_delta", 0)
        
        # Mine patterns
        patterns_learned = self._mine_patterns(
            pre_state, actions, success, health_delta
        )
        
        # Update Q-learning policies (if enabled)
        policies_updated = []
        if RL_ENABLED:
            policies_updated = self._update_rl_policies(
                pre_state, actions, post_state, success, health_delta
            )
        
        # Update success/failure statistics
        self._update_statistics(actions, success)
        
        # Periodically save knowledge base
        if self.learning_cycles % RL_UPDATE_FREQUENCY == 0:
            self._save_knowledge_base()
        
        enrichment_result = {
            "timestamp": datetime.datetime.now().isoformat(),
            "learning_cycle": self.learning_cycles,
            "patterns_learned": patterns_learned,
            "policies_updated": policies_updated,
            "knowledge_base_size": len(self.knowledge_base.get("patterns", {})),
            "q_table_size": len(self.q_table)
        }
        
        self.log(f"[ENRICH] Enrichment complete: "
                f"{len(patterns_learned)} patterns, "
                f"{len(policies_updated)} policies updated")
        
        return enrichment_result
    
    def _mine_patterns(self, pre_state: Dict, actions: List[Dict], 
                      success: bool, health_delta: float) -> List[Dict]:
        """
        Mine patterns from adaptation experience.
        
        Args:
            pre_state: System state before adaptation
            actions: Actions taken
            success: Whether adaptation succeeded
            health_delta: Change in health score
            
        Returns:
            List of learned pattern dictionaries
        """
        patterns = []
        
        # Extract state features
        derived_metrics = pre_state.get("derived_metrics", {})
        slo_violations = pre_state.get("slo_violations", [])
        
        # Create pattern signature
        for action in actions:
            pattern_key = self._create_pattern_key(derived_metrics, action)
            
            self.pattern_counts[pattern_key] += 1
            if success:
                self.pattern_successes[pattern_key] += 1
            
            # Calculate support and confidence
            support = self.pattern_counts[pattern_key]
            confidence = (self.pattern_successes[pattern_key] / support 
                         if support > 0 else 0)
            
            # If pattern meets thresholds, add to knowledge base
            if (support >= PATTERN_MINING_MIN_SUPPORT * 10 and 
                confidence >= PATTERN_MINING_MIN_CONFIDENCE):
                
                pattern = {
                    "pattern_key": pattern_key,
                    "action_type": action.get("name"),
                    "operation": action.get("operation"),
                    "support": support,
                    "confidence": confidence,
                    "avg_health_delta": health_delta
                }
                
                # Store in knowledge base
                if "patterns" not in self.knowledge_base:
                    self.knowledge_base["patterns"] = {}
                
                self.knowledge_base["patterns"][pattern_key] = pattern
                patterns.append(pattern)
        
        return patterns
    
    def _create_pattern_key(self, derived_metrics: Dict, action: Dict) -> str:
        """
        Create a unique key for a state-action pattern.
        
        Args:
            derived_metrics: Current derived metrics
            action: Action being taken
            
        Returns:
            Pattern key string
        """
        # Discretize metrics into ranges
        error_rate = derived_metrics.get("http.error.rate", 0)
        latency = derived_metrics.get("http.latency", 0)
        throughput = derived_metrics.get("http.throughput", 0)
        
        error_bucket = "high" if error_rate > 0.05 else "medium" if error_rate > 0.01 else "low"
        latency_bucket = "high" if latency > 1000 else "medium" if latency > 500 else "low"
        throughput_bucket = "high" if throughput > 50 else "medium" if throughput > 10 else "low"
        
        action_type = action.get("name", "unknown")
        operation = action.get("operation", "")
        
        return f"{error_bucket}_{latency_bucket}_{throughput_bucket}_{action_type}_{operation}"
    
    def _update_rl_policies(self, pre_state: Dict, actions: List[Dict],
                           post_state: Dict, success: bool, 
                           health_delta: float) -> List[str]:
        """
        Update reinforcement learning Q-values.
        
        Args:
            pre_state: State before adaptation
            actions: Actions taken
            post_state: State after adaptation
            success: Whether adaptation succeeded
            health_delta: Change in health score
            
        Returns:
            List of updated policy keys
        """
        updated_policies = []
        
        # Calculate reward
        reward = self._calculate_reward(health_delta, success)
        
        # Get state representations
        pre_state_key = self._get_state_key(pre_state)
        post_state_key = self._get_state_key(post_state)
        
        for action in actions:
            action_key = f"{action.get('name')}_{action.get('operation', '')}"
            q_key = (pre_state_key, action_key)
            
            # Current Q-value
            current_q = self.q_table.get(q_key, 0.0)
            
            # Get maximum Q-value for next state
            next_max_q = max(
                (self.q_table.get((post_state_key, a), 0.0) 
                 for a in self._get_possible_actions()),
                default=0.0
            )
            
            # Q-learning update
            new_q = (current_q + 
                    self.learning_rate * (reward + self.discount_factor * next_max_q - current_q))
            
            self.q_table[q_key] = new_q
            updated_policies.append(q_key)
        
        return [str(k) for k in updated_policies]
    
    def _calculate_reward(self, health_delta: float, success: bool) -> float:
        """
        Calculate reward for RL update.
        
        Args:
            health_delta: Change in health score
            success: Whether adaptation succeeded
            
        Returns:
            Reward value
        """
        # Base reward from health improvement
        reward = health_delta / 10.0  # Normalize
        
        # Bonus for success
        if success:
            reward += 10.0
        else:
            reward -= 5.0
        
        return reward
    
    def _get_state_key(self, state: Dict) -> str:
        """
        Get a discrete state key for Q-learning.
        
        Args:
            state: System state dictionary
            
        Returns:
            State key string
        """
        derived = state.get("derived_metrics", {})
        health = state.get("health_score", 100)
        
        # Discretize state features
        error_rate = derived.get("http.error.rate", 0)
        latency = derived.get("http.latency", 0)
        
        error_level = "high" if error_rate > 0.05 else "medium" if error_rate > 0.01 else "low"
        latency_level = "high" if latency > 1000 else "medium" if latency > 500 else "low"
        health_level = "critical" if health < 50 else "degraded" if health < 80 else "healthy"
        
        return f"{error_level}_{latency_level}_{health_level}"
    
    def _get_possible_actions(self) -> List[str]:
        """
        Get list of possible action keys.
        
        Returns:
            List of action key strings
        """
        return [
            "horizontal_increase",
            "horizontal_decrease",
            "vertical_increase",
            "vertical_decrease",
            "restart_"
        ]
    
    def _update_statistics(self, actions: List[Dict], success: bool):
        """
        Update success/failure statistics in knowledge base.
        
        Args:
            actions: Actions taken
            success: Whether adaptation succeeded
        """
        if "statistics" not in self.knowledge_base:
            self.knowledge_base["statistics"] = {
                "total_adaptations": 0,
                "successful_adaptations": 0,
                "action_counts": defaultdict(int),
                "action_successes": defaultdict(int)
            }
        
        stats = self.knowledge_base["statistics"]
        stats["total_adaptations"] += 1
        
        if success:
            stats["successful_adaptations"] += 1
        
        for action in actions:
            action_type = action.get("name", "unknown")
            stats["action_counts"][action_type] += 1
            
            if success:
                stats["action_successes"][action_type] += 1
    
    def get_best_action(self, state: Dict) -> Optional[str]:
        """
        Get best action for a given state based on learned Q-values.
        
        Args:
            state: Current system state
            
        Returns:
            Best action key or None
        """
        if not RL_ENABLED or not self.q_table:
            return None
        
        state_key = self._get_state_key(state)
        
        # Get Q-values for all actions in this state
        action_values = {}
        for action_key in self._get_possible_actions():
            q_key = (state_key, action_key)
            action_values[action_key] = self.q_table.get(q_key, 0.0)
        
        # Return action with highest Q-value
        if action_values:
            return max(action_values.items(), key=lambda x: x[1])[0]
        
        return None
    
    def get_knowledge_summary(self) -> Dict:
        """
        Get summary of knowledge base contents.
        
        Returns:
            Summary dictionary
        """
        stats = self.knowledge_base.get("statistics", {})
        
        total = stats.get("total_adaptations", 0)
        successful = stats.get("successful_adaptations", 0)
        
        return {
            "learning_cycles": self.learning_cycles,
            "total_patterns": len(self.knowledge_base.get("patterns", {})),
            "q_table_size": len(self.q_table),
            "total_adaptations": total,
            "successful_adaptations": successful,
            "success_rate": successful / total if total > 0 else 0,
            "action_statistics": dict(stats.get("action_counts", {}))
        }
    
    def _load_knowledge_base(self) -> Dict:
        """
        Load knowledge base from disk.
        
        Returns:
            Knowledge base dictionary
        """
        try:
            with open(self.knowledge_base_path, 'rb') as f:
                kb = pickle.load(f)
                self.log(f"[ENRICH] Loaded knowledge base from {self.knowledge_base_path}")
                return kb
        except FileNotFoundError:
            self.log(f"[ENRICH] No existing knowledge base found, creating new one")
            return {}
        except Exception as e:
            self.log(f"[ENRICH] Error loading knowledge base: {e}")
            return {}
    
    def _save_knowledge_base(self):
        """Save knowledge base to disk."""
        try:
            with open(self.knowledge_base_path, 'wb') as f:
                pickle.dump(self.knowledge_base, f)
            self.log(f"[ENRICH] Saved knowledge base to {self.knowledge_base_path}")
        except Exception as e:
            self.log(f"[ENRICH] Error saving knowledge base: {e}")
    
    def export_knowledge(self, filepath: str):
        """
        Export knowledge base in human-readable format.
        
        Args:
            filepath: Path to export file
        """
        export_data = {
            "metadata": {
                "export_time": datetime.datetime.now().isoformat(),
                "learning_cycles": self.learning_cycles
            },
            "summary": self.get_knowledge_summary(),
            "patterns": self.knowledge_base.get("patterns", {}),
            "statistics": self.knowledge_base.get("statistics", {})
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            self.log(f"[ENRICH] Exported knowledge to {filepath}")
        except Exception as e:
            self.log(f"[ENRICH] Error exporting knowledge: {e}")
    
    def log(self, message: str):
        """Log a message."""
        if self.logger:
            self.logger(message)
        else:
            print(message)
