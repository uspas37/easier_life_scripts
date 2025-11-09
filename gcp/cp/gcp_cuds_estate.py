#!/usr/bin/env python3
"""
GCP CUDs Estate Script
Searches across all GCP projects (excluding those starting with 'sys-')
and retrieves Committed Use Discount (CUD) details.
"""

import subprocess
import json
import sys
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


def run_command(cmd: List[str]) -> Dict[str, Any]:
    """Execute a shell command and return the output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return {"success": True, "output": result.stdout, "error": None}
    except subprocess.CalledProcessError as e:
        return {"success": False, "output": None, "error": e.stderr}
    except Exception as e:
        return {"success": False, "output": None, "error": str(e)}


def get_all_projects() -> List[Dict[str, str]]:
    """Retrieve all GCP projects."""
    print("Fetching all GCP projects...")
    cmd = ["gcloud", "projects", "list", "--format=json"]
    result = run_command(cmd)
    
    if not result["success"]:
        print(f"Error fetching projects: {result['error']}", file=sys.stderr)
        return []
    
    try:
        projects = json.loads(result["output"])
        return projects
    except json.JSONDecodeError as e:
        print(f"Error parsing projects JSON: {e}", file=sys.stderr)
        return []


def filter_projects(projects: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Filter out projects with IDs starting with 'sys-'."""
    filtered = [p for p in projects if not p.get("projectId", "").startswith("sys-")]
    print(f"Total projects: {len(projects)}")
    print(f"Filtered projects (excluding sys-*): {len(filtered)}")
    return filtered


def get_compute_cuds(project_id: str) -> List[Dict[str, Any]]:
    """Get Compute Engine CUDs for a project."""
    cmd = [
        "gcloud", "compute", "commitments", "list",
        f"--project={project_id}",
        "--format=json"
    ]
    result = run_command(cmd)
    
    if not result["success"]:
        return []
    
    try:
        cuds = json.loads(result["output"]) if result["output"].strip() else []
        return cuds
    except json.JSONDecodeError:
        return []


def get_project_cuds(project: Dict[str, str], progress_lock: Lock, counter: Dict[str, int], total: int) -> Dict[str, Any]:
    """Get all CUD details for a specific project."""
    project_id = project.get("projectId", "")
    project_name = project.get("name", "")
    
    compute_cuds = get_compute_cuds(project_id)
    
    # Thread-safe progress update
    with progress_lock:
        counter['completed'] += 1
        print(f"[{counter['completed']}/{total}] Checked project: {project_id} - Found {len(compute_cuds)} CUD(s)")
    
    return {
        "projectId": project_id,
        "projectName": project_name,
        "computeCUDs": compute_cuds,
        "totalCUDs": len(compute_cuds)
    }


def main():
    """Main function to orchestrate CUD discovery."""
    print("=" * 80)
    print("GCP Committed Use Discounts (CUDs) Estate Report")
    print("=" * 80)
    print()
    
    # Get and filter projects
    all_projects = get_all_projects()
    if not all_projects:
        print("No projects found or error occurred.", file=sys.stderr)
        sys.exit(1)
    
    filtered_projects = filter_projects(all_projects)
    if not filtered_projects:
        print("No projects to process after filtering.", file=sys.stderr)
        sys.exit(1)
    
    print()
    print("Scanning projects for CUDs in parallel...")
    print("-" * 80)
    
    # Collect CUD information from all projects
    all_project_results = []
    projects_with_cuds = []
    failed_projects = []
    
    # Thread-safe progress tracking
    progress_lock = Lock()
    counter = {'completed': 0}
    total_projects = len(filtered_projects)
    
    # Use ThreadPoolExecutor for parallel processing with more workers
    max_workers = min(20, total_projects)  # Cap at 20 or number of projects
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks simultaneously
        future_to_project = {
            executor.submit(get_project_cuds, project, progress_lock, counter, total_projects): project 
            for project in filtered_projects
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_project):
            project = future_to_project[future]
            try:
                cud_info = future.result()
                all_project_results.append(cud_info)
                if cud_info["totalCUDs"] > 0:
                    projects_with_cuds.append(cud_info)
            except Exception as e:
                failed_projects.append({
                    'projectId': project.get('projectId'),
                    'error': str(e)
                })
                with progress_lock:
                    print(f"Error processing project {project.get('projectId')}: {e}", file=sys.stderr)
    
    # Display results
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    if not projects_with_cuds:
        print("No CUDs found in any project.")
    else:
        print(f"Found CUDs in {len(projects_with_cuds)} project(s):")
        print()
        
        for project_info in projects_with_cuds:
            print(f"Project ID: {project_info['projectId']}")
            print(f"Project Name: {project_info['projectName']}")
            print(f"Total CUDs: {project_info['totalCUDs']}")
            print()
            
            if project_info['computeCUDs']:
                print("  Compute Engine CUDs:")
                for cud in project_info['computeCUDs']:
                    name = cud.get('name', 'N/A')
                    region = cud.get('region', 'N/A')
                    status = cud.get('status', 'N/A')
                    plan = cud.get('plan', 'N/A')
                    resources = cud.get('resources', [])
                    
                    print(f"    - Name: {name}")
                    print(f"      Region: {region}")
                    print(f"      Status: {status}")
                    print(f"      Plan: {plan}")
                    
                    if resources:
                        print(f"      Resources:")
                        for resource in resources:
                            res_type = resource.get('type', 'N/A')
                            amount = resource.get('amount', 'N/A')
                            print(f"        * Type: {res_type}, Amount: {amount}")
                    print()
            
            print("-" * 80)
    
    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total projects scanned: {len(filtered_projects)}")
    print(f"Successfully processed: {len(all_project_results)}")
    print(f"Failed: {len(failed_projects)}")
    print(f"Projects with CUDs: {len(projects_with_cuds)}")
    total_cuds = sum(p['totalCUDs'] for p in projects_with_cuds)
    print(f"Total CUDs found: {total_cuds}")
    
    if failed_projects:
        print()
        print("Failed Projects:")
        for failed in failed_projects:
            print(f"  - {failed['projectId']}: {failed['error']}")
    print()


if __name__ == "__main__":
    main()
