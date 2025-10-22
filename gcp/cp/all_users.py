#!/usr/bin/env python3
"""
GCP IAM Permissions Auditor

This script lists all GCP projects and retrieves IAM policy bindings
(users/service accounts with their assigned roles) for each project.
"""

import subprocess
import json
import sys
from typing import List, Dict, Any
from datetime import datetime


def run_command(command: List[str]) -> str:
    """
    Execute a shell command and return its output.
    
    Args:
        command: List of command arguments
        
    Returns:
        Command output as string
        
    Raises:
        subprocess.CalledProcessError: If command fails
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}", file=sys.stderr)
        print(f"Error message: {e.stderr}", file=sys.stderr)
        raise


def get_all_projects() -> List[str]:
    """
    Retrieve all GCP project IDs accessible to the current user.
    Projects starting with 'sys-' are filtered out.
    
    Returns:
        List of project IDs (excluding those starting with 'sys-')
    """
    print("Fetching all GCP projects...")
    output = run_command([
        "gcloud", "projects", "list",
        "--format=value(PROJECT_ID)"
    ])
    
    all_projects = [line.strip() for line in output.split('\n') if line.strip()]
    # Filter out projects starting with 'sys-'
    projects = [p for p in all_projects if not p.startswith('sys-')]
    
    excluded_count = len(all_projects) - len(projects)
    print(f"Found {len(all_projects)} projects (excluding {excluded_count} 'sys-*' projects)")
    print(f"Processing {len(projects)} projects\n")
    return projects


def get_project_iam_policy(project_id: str) -> Dict[str, Any]:
    """
    Retrieve IAM policy for a specific project.
    
    Args:
        project_id: GCP project ID
        
    Returns:
        Dictionary containing IAM policy bindings
    """
    try:
        output = run_command([
            "gcloud", "projects", "get-iam-policy", project_id,
            "--format=json"
        ])
        return json.loads(output)
    except subprocess.CalledProcessError:
        print(f"  ⚠️  Failed to get IAM policy for project: {project_id}", file=sys.stderr)
        return {}


def format_member(member: str) -> str:
    """
    Format member string for better readability.
    
    Args:
        member: Member identifier (e.g., user:email@example.com)
        
    Returns:
        Formatted member string
    """
    return member


def process_iam_policy(project_id: str, policy: Dict[str, Any]) -> None:
    """
    Process and display IAM policy bindings for a project.
    
    Args:
        project_id: GCP project ID
        policy: IAM policy dictionary
    """
    print(f"{'='*80}")
    print(f"Project: {project_id}")
    print(f"{'='*80}")
    
    if not policy or 'bindings' not in policy:
        print("  No IAM bindings found or unable to retrieve policy\n")
        return
    
    bindings = policy.get('bindings', [])
    
    if not bindings:
        print("  No IAM bindings found\n")
        return
    
    # Group members by role
    members_by_role = {}
    for binding in bindings:
        role = binding.get('role', 'Unknown')
        members = binding.get('members', [])
        
        if role not in members_by_role:
            members_by_role[role] = []
        
        members_by_role[role].extend(members)
    
    # Display results
    for role in sorted(members_by_role.keys()):
        print(f"\n  Role: {role}")
        print(f"  {'-'*76}")
        
        members = sorted(set(members_by_role[role]))
        for member in members:
            print(f"    • {format_member(member)}")
    
    print()


def export_to_json(results: List[Dict[str, Any]], output_file: str) -> None:
    """
    Export results to a JSON file.
    
    Args:
        results: List of project IAM policies
        output_file: Output file path
    """
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results exported to: {output_file}")


def export_to_csv(results: List[Dict[str, Any]], output_file: str) -> None:
    """
    Export results to a CSV file.
    
    Args:
        results: List of project IAM policies
        output_file: Output file path
    """
    import csv
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Project ID', 'Member', 'Role'])
        
        for result in results:
            project_id = result['project_id']
            policy = result['policy']
            
            if policy and 'bindings' in policy:
                for binding in policy['bindings']:
                    role = binding.get('role', 'Unknown')
                    members = binding.get('members', [])
                    
                    for member in members:
                        writer.writerow([project_id, member, role])
    
    print(f"✓ Results exported to: {output_file}")


def main():
    """
    Main function to orchestrate the IAM audit process.
    """
    print("GCP IAM Permissions Auditor")
    print("="*80)
    print()
    
    try:
        # Get all projects
        projects = get_all_projects()
        
        if not projects:
            print("No projects found or unable to list projects.")
            sys.exit(1)
        
        # Store results for export
        results = []
        
        # Process each project
        for i, project_id in enumerate(projects, 1):
            print(f"\n[{i}/{len(projects)}] Processing project: {project_id}")
            policy = get_project_iam_policy(project_id)
            process_iam_policy(project_id, policy)
            
            results.append({
                'project_id': project_id,
                'policy': policy
            })
        
        # Automatically export results to CSV
        print("\n" + "="*80)
        print("Audit complete!")
        print("="*80)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"iam_audit_{timestamp}.csv"
        
        print(f"\nExporting results to CSV...")
        export_to_csv(results, output_file)
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

