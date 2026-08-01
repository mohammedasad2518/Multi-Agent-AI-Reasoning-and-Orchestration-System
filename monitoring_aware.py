#!/usr/bin/env python3

"""
AURORA: Agentic Unified Runtime for Orchestrated Resilient Adaptation

Main monitoring script that implements the AWARE framework for autonomous
runtime management of cloud-based microservices.

Instead of traditional MAPE-K loop, this uses:
- Assess Agent: Monitor and detect anomalies
- Weigh Agent: Evaluate and plan adaptations
- Act Agent: Execute adaptations
- Reflect Agent: Evaluate outcomes
- Enrich Agent: Learn and improve over time
"""

import sys
import time
import datetime
import shutil
import os
from typing import List, Optional

from utils import *
from constants import *
from aware_orchestrator import AWAREOrchestrator


def clear_charts():
    """Clear the charts folder for fresh visualization."""
    charts_folder = "charts/"
    if os.path.exists(charts_folder):
        shutil.rmtree(charts_folder) 
        os.makedirs(charts_folder)
    else:
        os.makedirs(charts_folder)


def run_monitoring_cycle(orchestrator: AWAREOrchestrator, 
                        metrics: List[dict],
                        pods: List[str]) -> dict:
    """
    Run one complete monitoring cycle across all pods.
    
    Args:
        orchestrator: AWARE orchestrator instance
        metrics: List of metrics to monitor
        pods: List of pod names to monitor
        
    Returns:
        Dictionary mapping service names to cycle results
    """
    print(f"\n{'='*80}")
    print(f"MONITORING CYCLE - {datetime.datetime.now()}")
    print(f"{'='*80}")
    
    all_results = {}
    
    for pod in pods:
        # Build Sysdig scope for this pod
        scope = f"kubernetes.namespace.name='{NAMESPACE}' and kubernetes.pod.name='{pod}'"
        
        # Normalize service name
        service = normalize_service_name(pod)
        
        print(f"\n--- Monitoring {service} (pod: {pod}) ---")
        
        # Run AWARE cycle for this service
        cycle_result = orchestrator.run_aware_cycle(metrics, service, scope=scope)
        
        all_results[service] = cycle_result
        
        # Brief summary
        status = cycle_result.get("status", "unknown")
        print(f"    Status: {status}")
        
        if status == "completed":
            health_delta = cycle_result.get("phases", {}).get("reflect", {}).get("health_delta", 0)
            print(f"    Health Δ: {health_delta:+.1f}")
    
    return all_results


def main():
    """Main execution function."""
    print("\n" + "="*80)
    print(" AURORA - Agentic Unified Runtime for Orchestrated Resilient Adaptation")
    print("="*80)
    print(" Based on AWARE framework: Assess → Weigh → Act → Reflect → Enrich")
    print("="*80 + "\n")
    
    # Clear old charts
    clear_charts()
    
    # Initialize Sysdig client
    print("[INIT] Initializing Sysdig client...")
    sdclient = get_client(DEFAULT_URL, DEFAULT_APIKEY, DEFAULT_GUID)
    
    # Get list of pods
    print(f"[INIT] Discovering pods in namespace '{NAMESPACE}'...")
    pods = get_pods(NAMESPACE)
    print(f"[INIT] Found {len(pods)} pods: {', '.join(pods)}")
    
    # Initialize AWARE orchestrator
    print("[INIT] Initializing AWARE orchestrator and agents...")
    orchestrator = AWAREOrchestrator(sdclient)
    
    print("\n[INIT] Initialization complete. Starting monitoring loop...\n")
    
    cycle_counter = 0
    
    try:
        while True:
            cycle_counter += 1
            cycle_start = time.time()
            
            print(f"\n{'#'*80}")
            print(f"# MONITORING CYCLE {cycle_counter}")
            print(f"{'#'*80}")
            
            # Run monitoring for all pods
            results = run_monitoring_cycle(orchestrator, METRICS, pods)
            
            # Print cycle summary
            print(f"\n--- Cycle Summary ---")
            total_adaptations = sum(
                1 for r in results.values() 
                if r.get("status") == "completed"
            )
            successful_adaptations = sum(
                1 for r in results.values()
                if r.get("adaptation_success", False)
            )
            
            print(f"  Services monitored: {len(results)}")
            print(f"  Adaptations performed: {total_adaptations}")
            print(f"  Successful adaptations: {successful_adaptations}")
            
            # Get overall knowledge summary every 5 cycles
            if cycle_counter % 5 == 0:
                summary = orchestrator.get_cycle_summary(lookback=5)
                knowledge = summary.get("knowledge_summary", {})
                
                print(f"\n--- Learning Summary (Last 5 cycles) ---")
                print(f"  Total patterns learned: {knowledge.get('total_patterns', 0)}")
                print(f"  Q-table size: {knowledge.get('q_table_size', 0)}")
                print(f"  Adaptation success rate: {knowledge.get('success_rate', 0):.1%}")
            
            # Export knowledge periodically
            if cycle_counter % 10 == 0:
                export_path = f"knowledge_export_cycle_{cycle_counter}.json"
                orchestrator.export_knowledge(export_path)
                print(f"\n[EXPORT] Knowledge base exported to {export_path}")
            
            cycle_duration = time.time() - cycle_start
            print(f"\n[TIMING] Cycle completed in {cycle_duration:.2f}s")
            
            # Wait before next cycle
            sleep_time = max(INTERVAL - int(cycle_duration), 10)
            print(f"[WAIT] Sleeping {sleep_time}s before next cycle...\n")
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\n\n[SHUTDOWN] Received interrupt signal")
        print("[SHUTDOWN] Exporting final knowledge base...")
        orchestrator.export_knowledge("knowledge_export_final.json")
        print("[SHUTDOWN] Monitoring stopped by user")
        
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print("[SHUTDOWN] Exporting knowledge base before exit...")
        try:
            orchestrator.export_knowledge("knowledge_export_error.json")
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
