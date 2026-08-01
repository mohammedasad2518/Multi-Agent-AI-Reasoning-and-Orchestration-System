"""
AWARE Orchestrator - AWARE Framework

This orchestrator coordinates the five AWARE agents (Assess, Weigh, Act, Reflect, Enrich)
to implement a complete self-adaptive control loop for cloud-based microservices.

The orchestrator:
- Initializes all agents
- Coordinates the AWARE cycle
- Manages shared knowledge base
- Logs all agent activities
- Handles errors and failures gracefully
"""

import datetime
import time
from typing import Dict, List, Optional
import csv
import os

from assess_agent import AssessAgent
from weigh_agent import WeighAgent
from act_agent import ActAgent
from reflect_agent import ReflectAgent
from enrich_agent import EnrichAgent

from constants import AWARE_LOG_FILE, AGENT_TIMEOUT


class AWAREOrchestrator:
    """
    Orchestrates the AWARE loop across all agents.
    """
    
    def __init__(self, sysdig_client, logger=None):
        """
        Initialize the AWARE orchestrator.
        
        Args:
            sysdig_client: Sysdig client for monitoring
            logger: Optional logger function
        """
        self.logger = logger
        self.sysdig_client = sysdig_client
        
        # Initialize shared knowledge base
        self.knowledge_base = {}
        
        # Initialize all agents
        self.log("[ORCHESTRATOR] Initializing AWARE agents")
        
        self.assess_agent = AssessAgent(sysdig_client, logger=self.log)
        self.enrich_agent = EnrichAgent(logger=self.log)
        self.weigh_agent = WeighAgent(
            knowledge_base=self.enrich_agent.knowledge_base,
            logger=self.log
        )
        self.act_agent = ActAgent(logger=self.log)
        self.reflect_agent = ReflectAgent(logger=self.log)
        
        # Cycle counter
        self.cycle_count = 0
        
        # Initialize log file
        self._initialize_log_file()
    
    def run_aware_cycle(self, metrics: List[dict], service: str, 
                       scope: Optional[str] = None) -> Dict:
        """
        Execute one complete AWARE cycle.
        
        Args:
            metrics: List of metric definitions to monitor
            service: Service name
            scope: Optional Sysdig scope filter
            
        Returns:
            Dictionary containing results from all phases
        """
        self.cycle_count += 1
        cycle_start = datetime.datetime.now()
        
        self.log(f"\n{'='*80}")
        self.log(f"[ORCHESTRATOR] Starting AWARE Cycle #{self.cycle_count} for {service}")
        self.log(f"{'='*80}")
        
        cycle_result = {
            "cycle_number": self.cycle_count,
            "service": service,
            "start_time": cycle_start.isoformat(),
            "phases": {}
        }
        
        try:
            # Phase 1: ASSESS
            self.log(f"\n[ORCHESTRATOR] Phase 1/5: ASSESS")
            assess_start = time.time()
            
            system_snapshot = self.assess_agent.assess(metrics, service, scope)
            
            if not system_snapshot:
                self.log("[ORCHESTRATOR] Assessment failed - aborting cycle")
                cycle_result["status"] = "aborted"
                cycle_result["reason"] = "Assessment failed"
                return cycle_result
            
            cycle_result["phases"]["assess"] = {
                "duration": time.time() - assess_start,
                "health_score": system_snapshot.get("health_score", 0),
                "slo_violations": len(system_snapshot.get("slo_violations", [])),
                "anomalies": len(system_snapshot.get("anomalies", {}))
            }
            
            # Phase 2: WEIGH
            self.log(f"\n[ORCHESTRATOR] Phase 2/5: WEIGH")
            weigh_start = time.time()
            
            decision = self.weigh_agent.weigh(system_snapshot, service)
            
            cycle_result["phases"]["weigh"] = {
                "duration": time.time() - weigh_start,
                "actions_planned": len(decision.get("actions", [])),
                "confidence": decision.get("confidence", 0)
            }
            
            # Check if any actions are needed
            if not decision.get("actions"):
                self.log("[ORCHESTRATOR] No actions needed - system is stable")
                cycle_result["status"] = "stable"
                cycle_result["reason"] = "No adaptations required"
                
                # Log to CSV
                self._log_to_csv(cycle_result, system_snapshot, None, None, None, None)
                
                return cycle_result
            
            # Phase 3: ACT
            self.log(f"\n[ORCHESTRATOR] Phase 3/5: ACT")
            act_start = time.time()
            
            execution_result = self.act_agent.act(decision)
            
            cycle_result["phases"]["act"] = {
                "duration": time.time() - act_start,
                "success": execution_result.get("success", False),
                "actions_executed": execution_result.get("actions_executed", 0)
            }
            
            # Wait for system to stabilize after adaptation
            self.log("[ORCHESTRATOR] Waiting for system stabilization...")
            time.sleep(30)  # Wait 30 seconds
            
            # Reassess system after adaptation
            self.log("[ORCHESTRATOR] Reassessing system state post-adaptation")
            post_snapshot = self.assess_agent.assess(metrics, service, scope)
            
            if not post_snapshot:
                self.log("[ORCHESTRATOR] Post-adaptation assessment failed")
                post_snapshot = system_snapshot  # Use pre-state as fallback
            
            # Phase 4: REFLECT
            self.log(f"\n[ORCHESTRATOR] Phase 4/5: REFLECT")
            reflect_start = time.time()
            
            reflection = self.reflect_agent.reflect(
                system_snapshot, post_snapshot, decision, execution_result
            )
            
            cycle_result["phases"]["reflect"] = {
                "duration": time.time() - reflect_start,
                "success": reflection.get("success", False),
                "health_delta": reflection.get("health_delta", 0),
                "improvements": len(reflection.get("improvements", [])),
                "degradations": len(reflection.get("degradations", []))
            }
            
            # Phase 5: ENRICH
            self.log(f"\n[ORCHESTRATOR] Phase 5/5: ENRICH")
            enrich_start = time.time()
            
            enrichment = self.enrich_agent.enrich(
                reflection, decision, system_snapshot, post_snapshot
            )
            
            cycle_result["phases"]["enrich"] = {
                "duration": time.time() - enrich_start,
                "patterns_learned": len(enrichment.get("patterns_learned", [])),
                "policies_updated": len(enrichment.get("policies_updated", []))
            }
            
            # Overall cycle status
            cycle_result["status"] = "completed"
            cycle_result["adaptation_success"] = reflection.get("success", False)
            
            # Log to CSV
            self._log_to_csv(cycle_result, system_snapshot, decision, 
                           execution_result, reflection, enrichment)
            
        except Exception as e:
            self.log(f"[ORCHESTRATOR] Error in AWARE cycle: {e}")
            cycle_result["status"] = "error"
            cycle_result["error"] = str(e)
            
        finally:
            cycle_duration = (datetime.datetime.now() - cycle_start).total_seconds()
            cycle_result["total_duration"] = cycle_duration
            
            self.log(f"\n[ORCHESTRATOR] Cycle #{self.cycle_count} completed in {cycle_duration:.2f}s")
            self.log(f"[ORCHESTRATOR] Status: {cycle_result['status']}")
        
        return cycle_result
    
    def _initialize_log_file(self):
        """Initialize the AWARE cycle log file with headers."""
        if not os.path.exists(AWARE_LOG_FILE):
            with open(AWARE_LOG_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "cycle_number", "service", "status",
                    "health_score_pre", "health_score_post", "health_delta",
                    "slo_violations", "anomalies", "actions_planned",
                    "actions_executed", "adaptation_success",
                    "patterns_learned", "policies_updated",
                    "cycle_duration"
                ])
    
    def _log_to_csv(self, cycle_result: Dict, pre_state: Dict,
                    decision: Optional[Dict], execution: Optional[Dict],
                    reflection: Optional[Dict], enrichment: Optional[Dict]):
        """
        Log cycle results to CSV file.
        
        Args:
            cycle_result: Overall cycle result
            pre_state: Pre-adaptation state
            decision: Weigh agent decision
            execution: Act agent execution result
            reflection: Reflect agent reflection
            enrichment: Enrich agent enrichment result
        """
        try:
            with open(AWARE_LOG_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                
                health_pre = pre_state.get("health_score", 0) if pre_state else 0
                health_post = 0
                health_delta = 0
                
                if reflection:
                    health_post = reflection.get("post_health", 0)
                    health_delta = reflection.get("health_delta", 0)
                
                writer.writerow([
                    datetime.datetime.now().isoformat(),
                    cycle_result.get("cycle_number", 0),
                    cycle_result.get("service", "unknown"),
                    cycle_result.get("status", "unknown"),
                    health_pre,
                    health_post,
                    health_delta,
                    len(pre_state.get("slo_violations", [])) if pre_state else 0,
                    len(pre_state.get("anomalies", {})) if pre_state else 0,
                    len(decision.get("actions", [])) if decision else 0,
                    execution.get("actions_executed", 0) if execution else 0,
                    reflection.get("success", False) if reflection else False,
                    len(enrichment.get("patterns_learned", [])) if enrichment else 0,
                    len(enrichment.get("policies_updated", [])) if enrichment else 0,
                    cycle_result.get("total_duration", 0)
                ])
        except Exception as e:
            self.log(f"[ORCHESTRATOR] Error logging to CSV: {e}")
    
    def get_cycle_summary(self, lookback: int = 10) -> Dict:
        """
        Get summary of recent AWARE cycles.
        
        Args:
            lookback: Number of recent cycles to analyze
            
        Returns:
            Summary dictionary
        """
        # Get summaries from each agent
        reflect_summary = self.reflect_agent.get_reflection_summary(lookback)
        knowledge_summary = self.enrich_agent.get_knowledge_summary()
        
        return {
            "total_cycles": self.cycle_count,
            "reflection_summary": reflect_summary,
            "knowledge_summary": knowledge_summary
        }
    
    def export_knowledge(self, filepath: str = "aware_knowledge_export.json"):
        """
        Export learned knowledge in human-readable format.
        
        Args:
            filepath: Path to export file
        """
        self.enrich_agent.export_knowledge(filepath)
        self.log(f"[ORCHESTRATOR] Exported knowledge to {filepath}")
    
    def log(self, message: str):
        """Log a message."""
        if self.logger:
            self.logger(message)
        else:
            print(message)
