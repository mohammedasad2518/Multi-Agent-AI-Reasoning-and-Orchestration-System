"""
Act Agent - AWARE Framework

This agent executes chosen adaptations such as scaling pods, restarting failed services,
or reallocating containers through Kubernetes APIs.

Responsibilities:
- Execute horizontal scaling (replica adjustments)
- Execute vertical scaling (resource adjustments)
- Restart services when needed
- Validate execution success
"""

import subprocess
import time
from typing import List, Dict, Optional
from kubernetes import config
from openshift.dynamic import DynamicClient
from kubernetes.dynamic.exceptions import ConflictError

from constants import NAMESPACE, MAX_PODS


class ActAgent:
    """
    The Act Agent executes adaptation decisions.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the Act Agent.
        
        Args:
            logger: Optional logger for agent activities
        """
        self.logger = logger
        self.execution_history = []
        
        # Initialize Kubernetes client
        try:
            k8s_client = config.new_client_from_config()
            self.dyn_client = DynamicClient(k8s_client)
            self.v1_deployments = self.dyn_client.resources.get(
                api_version='apps/v1', kind='Deployment'
            )
        except Exception as e:
            self.log(f"[ACT] Warning: Failed to initialize K8s client: {e}")
            self.dyn_client = None
            self.v1_deployments = None
    
    def act(self, decision: Dict) -> Dict:
        """
        Execute actions from Weigh Agent's decision.
        
        Args:
            decision: Decision dictionary from Weigh Agent
            
        Returns:
            Dictionary containing:
            - success: Whether all actions succeeded
            - results: Individual action results
            - errors: Any errors encountered
        """
        actions = decision.get("actions", [])
        service = decision.get("service", "unknown")
        
        self.log(f"[ACT] Executing {len(actions)} actions for {service}")
        
        results = []
        errors = []
        all_success = True
        
        for action in actions:
            try:
                result = self._execute_action(action)
                results.append(result)
                
                if not result.get("success", False):
                    all_success = False
                    errors.append(result.get("error", "Unknown error"))
                    
            except Exception as e:
                self.log(f"[ACT] Exception executing action {action['name']}: {e}")
                errors.append(str(e))
                all_success = False
                results.append({
                    "action": action["name"],
                    "success": False,
                    "error": str(e)
                })
        
        execution_result = {
            "success": all_success,
            "actions_executed": len(actions),
            "results": results,
            "errors": errors if errors else None
        }
        
        self.execution_history.append(execution_result)
        
        self.log(f"[ACT] Execution complete: {'SUCCESS' if all_success else 'FAILED'}")
        
        return execution_result
    
    def _execute_action(self, action: Dict) -> Dict:
        """
        Execute a single action.
        
        Args:
            action: Action dictionary
            
        Returns:
            Result dictionary
        """
        action_type = action.get("name")
        
        if action_type == "horizontal":
            return self._horizontal_scale(action)
        elif action_type == "vertical":
            return self._vertical_scale(action)
        elif action_type == "restart":
            return self._restart_service(action)
        else:
            return {
                "action": action_type,
                "success": False,
                "error": f"Unknown action type: {action_type}"
            }
    
    def _horizontal_scale(self, action: Dict) -> Dict:
        """
        Execute horizontal scaling (replica adjustment).
        
        Args:
            action: Action dictionary with operation and amount
            
        Returns:
            Result dictionary
        """
        service = action.get("service")
        operation = action.get("operation")
        amount = action.get("amount", 1)
        
        self.log(f"[ACT] Horizontal scaling: {operation} {service} by {amount}")
        
        try:
            # Get current replica count
            result = subprocess.run(
                ["oc", "get", "deployment", service, "-o", "jsonpath={.spec.replicas}"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return {
                    "action": "horizontal",
                    "success": False,
                    "error": f"Failed to get current replicas: {result.stderr}"
                }
            
            try:
                curr_replicas = int(result.stdout.strip())
            except ValueError:
                return {
                    "action": "horizontal",
                    "success": False,
                    "error": f"Invalid replica count: {result.stdout}"
                }
            
            # Calculate new replica count
            if operation == "increase":
                new_count = min(curr_replicas + amount, MAX_PODS)
            else:  # decrease
                new_count = max(curr_replicas - amount, 1)
            
            # Execute scaling
            scale_result = subprocess.run(
                ["oc", "scale", "deployment", service, f"--replicas={new_count}"],
                capture_output=True, text=True, timeout=10
            )
            
            if scale_result.returncode != 0:
                return {
                    "action": "horizontal",
                    "success": False,
                    "error": f"Failed to scale: {scale_result.stderr}"
                }
            
            self.log(f"[ACT] Scaled {service} from {curr_replicas} to {new_count} replicas")
            
            return {
                "action": "horizontal",
                "success": True,
                "service": service,
                "previous_replicas": curr_replicas,
                "new_replicas": new_count,
                "message": f"Scaled from {curr_replicas} to {new_count} replicas"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "action": "horizontal",
                "success": False,
                "error": "Command timeout"
            }
        except Exception as e:
            return {
                "action": "horizontal",
                "success": False,
                "error": str(e)
            }
    
    def _vertical_scale(self, action: Dict) -> Dict:
        """
        Execute vertical scaling (resource adjustment).
        
        Args:
            action: Action dictionary with resource and factor
            
        Returns:
            Result dictionary
        """
        service = action.get("service")
        operation = action.get("operation")
        factor = action.get("factor", 1.0)
        
        self.log(f"[ACT] Vertical scaling: {operation} {service} by {factor}x")
        
        if not self.v1_deployments:
            return {
                "action": "vertical",
                "success": False,
                "error": "Kubernetes client not initialized"
            }
        
        try:
            def modify_resources(deployment):
                """Modify resource requests and limits."""
                for container in deployment.spec.template.spec.containers:
                    for resource_type in ['cpu', 'memory']:
                        # Adjust requests
                        if (container.resources.requests and 
                            resource_type in container.resources.requests):
                            old_val = container.resources.requests[resource_type]
                            scale_factor = factor if operation == 'increase' else 1/factor
                            new_val = self._adjust_resource_value(old_val, scale_factor)
                            container.resources.requests[resource_type] = new_val
                        
                        # Adjust limits
                        if (container.resources.limits and 
                            resource_type in container.resources.limits):
                            old_val = container.resources.limits[resource_type]
                            scale_factor = factor if operation == 'increase' else 1/factor
                            new_val = self._adjust_resource_value(old_val, scale_factor)
                            container.resources.limits[resource_type] = new_val
            
            success = self._retry_deployment_patch(service, modify_resources)
            
            if success:
                return {
                    "action": "vertical",
                    "success": True,
                    "service": service,
                    "factor": factor,
                    "message": f"Adjusted resources by {factor}x"
                }
            else:
                return {
                    "action": "vertical",
                    "success": False,
                    "error": "Failed to update deployment after retries"
                }
                
        except Exception as e:
            return {
                "action": "vertical",
                "success": False,
                "error": str(e)
            }
    
    def _restart_service(self, action: Dict) -> Dict:
        """
        Restart a service by rolling restart of pods.
        
        Args:
            action: Action dictionary
            
        Returns:
            Result dictionary
        """
        service = action.get("service")
        
        self.log(f"[ACT] Restarting service: {service}")
        
        try:
            result = subprocess.run(
                ["oc", "rollout", "restart", "deployment", service],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return {
                    "action": "restart",
                    "success": False,
                    "error": f"Failed to restart: {result.stderr}"
                }
            
            self.log(f"[ACT] Successfully triggered restart for {service}")
            
            return {
                "action": "restart",
                "success": True,
                "service": service,
                "message": "Restart triggered successfully"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "action": "restart",
                "success": False,
                "error": "Command timeout"
            }
        except Exception as e:
            return {
                "action": "restart",
                "success": False,
                "error": str(e)
            }
    
    def _adjust_resource_value(self, old_value: str, factor: float) -> str:
        """
        Adjust a resource value (CPU/memory) by a scaling factor.
        
        Args:
            old_value: Original resource value (e.g., "500m", "1Gi")
            factor: Scaling factor
            
        Returns:
            New resource value as string
        """
        try:
            if old_value.endswith('m'):  # millicores
                base = float(old_value[:-1])
                new_val = int(base * factor)
                return f"{new_val}m"
            elif old_value.endswith('Mi'):  # Mebibytes
                base = float(old_value[:-2])
                new_val = int(base * factor)
                return f"{new_val}Mi"
            elif old_value.endswith('Gi'):  # Gibibytes
                base = float(old_value[:-2])
                new_val = int(base * factor)
                return f"{new_val}Gi"
            else:  # Assume cores or bytes
                base = float(old_value)
                new_val = round(base * factor, 2)
                return str(new_val)
        except Exception as e:
            self.log(f"[ACT] Error adjusting resource {old_value}: {e}")
            return old_value
    
    def _retry_deployment_patch(self, deployment_name: str, 
                                modify_fn, max_retries: int = 3) -> bool:
        """
        Attempt to patch a deployment with retries for conflict resolution.
        
        Args:
            deployment_name: Name of deployment to patch
            modify_fn: Function to modify deployment object
            max_retries: Maximum retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                deployment = self.v1_deployments.get(
                    name=deployment_name, namespace=NAMESPACE
                )
                modify_fn(deployment)
                self.v1_deployments.patch(
                    body=deployment.to_dict(), namespace=NAMESPACE
                )
                self.log(f"[ACT] Successfully updated deployment {deployment_name}")
                return True
                
            except ConflictError:
                self.log(f"[ACT] Conflict updating {deployment_name}, "
                        f"retry {attempt + 1}/{max_retries}")
                time.sleep(1 + attempt * 0.5)
                
            except Exception as e:
                self.log(f"[ACT] Error updating {deployment_name}: {e}")
                return False
        
        self.log(f"[ACT] Exceeded retries for {deployment_name}")
        return False
    
    def get_execution_history(self, lookback: int = 10) -> List[Dict]:
        """
        Retrieve recent execution history.
        
        Args:
            lookback: Number of past executions to retrieve
            
        Returns:
            List of execution result dictionaries
        """
        return self.execution_history[-lookback:]
    
    def log(self, message: str):
        """Log a message."""
        if self.logger:
            self.logger(message)
        else:
            print(message)
