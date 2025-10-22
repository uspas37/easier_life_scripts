#!/usr/bin/env python3
"""
GCP Organization IAM User Permissions Exporter

This script searches all IAM policies across a GCP organization for user accounts
and exports the results to a CSV file with user, resource, and role information.
"""

import subprocess
import json
import csv
import sys
from datetime import datetime
from typing import List, Dict, Any


def run_gcloud_command(command: List[str]) -> str:
    """
    Execute a gcloud command and return its output.
    
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


def search_all_iam_policies(org_id: str) -> List[Dict[str, Any]]:
    """
    Search all IAM policies in the organization for user accounts.
    
    Args:
        org_id: GCP organization ID
        
    Returns:
        List of IAM policy results
    """
    print(f"Searching IAM policies across organization {org_id}...")
    print("This may take a few moments...\n")
    
    command = [
        "gcloud", "asset", "search-all-iam-policies",
        f"--scope=organizations/{org_id}",
        "--query=memberTypes=user",
        "--order-by=resource",
        "--format=json"
    ]
    
    output = run_gcloud_command(command)
    
    if not output:
        return []
    
    try:
        results = json.loads(output)
        return results if isinstance(results, list) else []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}", file=sys.stderr)
        return []


def extract_project_id(resource: str) -> str:
    """
    Extract project ID from a GCP resource path.
    
    Args:
        resource: GCP resource path (e.g., //cloudresourcemanager.googleapis.com/projects/my-project)
        
    Returns:
        Project ID or 'N/A' if not found
    """
    # Common patterns:
    # //cloudresourcemanager.googleapis.com/projects/PROJECT_ID
    # //compute.googleapis.com/projects/PROJECT_ID/...
    # projects/PROJECT_ID/...
    
    if '/projects/' in resource:
        parts = resource.split('/projects/')
        if len(parts) > 1:
            # Get the part after '/projects/'
            project_part = parts[1]
            # Extract just the project ID (before next slash if any)
            project_id = project_part.split('/')[0]
            return project_id
    
    return 'N/A'


def parse_iam_results(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Parse IAM policy search results into a flat structure for CSV export.
    
    Args:
        results: Raw IAM policy search results
        
    Returns:
        List of dictionaries with user, resource, and permission information
    """
    parsed_data = []
    
    for result in results:
        resource = result.get('resource', 'Unknown')
        policy = result.get('policy', {})
        bindings = policy.get('bindings', [])
        
        # Extract project ID from resource path
        project_id = extract_project_id(resource)
        
        for binding in bindings:
            role = binding.get('role', 'Unknown')
            members = binding.get('members', [])
            
            # Filter for user accounts only
            user_members = [m for m in members if m.startswith('user:')]
            
            for member in user_members:
                # Extract email from "user:email@example.com" format
                user_email = member.split(':', 1)[1] if ':' in member else member
                
                parsed_data.append({
                    'user_email': user_email,
                    'project_id': project_id,
                    'resource': resource,
                    'role': role,
                    'member_full': member
                })
    
    return parsed_data


def export_to_csv(data: List[Dict[str, str]], output_file: str) -> None:
    """
    Export parsed IAM data to a CSV file.
    
    Args:
        data: List of dictionaries containing user and permission information
        output_file: Output CSV file path
    """
    if not data:
        print("No data to export.")
        return
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['User Email', 'Project ID', 'Resource', 'Role'])
        
        # Write data rows
        for row in data:
            writer.writerow([
                row['user_email'],
                row['project_id'],
                row['resource'],
                row['role']
            ])
    
    print(f"✓ Successfully exported {len(data)} records to: {output_file}")


def main():
    """
    Main function to orchestrate the IAM policy search and export.
    """
    print("="*80)
    print("GCP Organization IAM User Permissions Exporter")
    print("="*80)
    print()
    
    # Organization ID
    org_id = "775078138164"
    
    try:
        # Search all IAM policies for users
        results = search_all_iam_policies(org_id)
        
        if not results:
            print("No IAM policies found or unable to retrieve data.")
            sys.exit(1)
        
        print(f"Found {len(results)} IAM policy results")
        print("Parsing user permissions...\n")
        
        # Parse results into flat structure
        parsed_data = parse_iam_results(results)
        
        if not parsed_data:
            print("No user accounts found in IAM policies.")
            sys.exit(0)
        
        print(f"Extracted {len(parsed_data)} user permission entries")
        
        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"org_iam_users_{timestamp}.csv"
        
        # Export to CSV
        print(f"\nExporting to CSV...")
        export_to_csv(parsed_data, output_file)
        
        print("\n" + "="*80)
        print("Export complete!")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

