#!/usr/bin/env python3
"""
Check GCP IAM users in colpal-shared-resources-prd project
and identify users with no activity in the last 90 days.
"""
import subprocess
import json
import csv
from datetime import datetime, timedelta
from collections import defaultdict

PROJECT_ID = "colpal-shared-resources-prd"
DAYS = 90


def is_human_user(member):
    """Check if a member is a human user (not a service account or group)."""
    # Service accounts: serviceAccount:*@*.iam.gserviceaccount.com
    # Groups: group:*
    # Domains: domain:*
    # Human users: user:* or just email addresses
    
    if member.startswith('serviceAccount:'):
        return False
    if member.startswith('group:'):
        return False
    if member.startswith('domain:'):
        return False
    if member.startswith('deleted:'):
        return False
    
    # Accept user: prefix or plain email addresses
    return True


def get_iam_members():
    """Fetch all IAM members and their roles from the project."""
    print(f"Fetching IAM policy for project: {PROJECT_ID}...")
    
    cmd = [
        "gcloud", "projects", "get-iam-policy", PROJECT_ID,
        "--format=json"
    ]
    
    try:
        output = subprocess.check_output(cmd, text=True)
        policy = json.loads(output)
        
        # Build member -> roles mapping (human users only)
        member_roles = defaultdict(list)
        service_account_count = 0
        
        for binding in policy.get("bindings", []):
            role = binding.get("role", "")
            for member in binding.get("members", []):
                if member and member != "*":
                    if is_human_user(member):
                        member_roles[member].append(role)
                    else:
                        service_account_count += 1
        
        print(f"Found {len(member_roles)} human users (excluded {service_account_count} service accounts/groups)")
        return member_roles
    
    except subprocess.CalledProcessError as e:
        print(f"Error fetching IAM policy: {e}")
        return {}


def get_user_activity():
    """Fetch user activity from Cloud Audit Logs for the last 90 days."""
    print(f"Fetching audit logs for the last {DAYS} days...")
    
    # Calculate the date 90 days ago
    cutoff_date = datetime.now() - timedelta(days=DAYS)
    
    cmd = [
        "gcloud", "logging", "read",
        'logName:"cloudaudit.googleapis.com" AND protoPayload.authenticationInfo.principalEmail:*',
        f"--project={PROJECT_ID}",
        f"--freshness={DAYS}d",
        "--order=desc",
        "--format=json",
        "--limit=200000"
    ]
    
    try:
        output = subprocess.check_output(cmd, text=True)
        logs = json.loads(output)
        
        # Build activity tracking: email -> {count, last_seen}
        activity = {}
        for log in logs:
            try:
                email = log.get("protoPayload", {}).get("authenticationInfo", {}).get("principalEmail")
                timestamp = log.get("timestamp")
                
                if email and timestamp:
                    # Only track human users
                    member_id = f"user:{email}" if not email.startswith("user:") else email
                    if is_human_user(member_id):
                        if email not in activity:
                            activity[email] = {"count": 0, "last_seen": timestamp}
                        
                        activity[email]["count"] += 1
                        
                        # Keep the most recent timestamp
                        if timestamp > activity[email]["last_seen"]:
                            activity[email]["last_seen"] = timestamp
            except Exception as e:
                continue
        
        print(f"Found activity for {len(activity)} principals")
        return activity
    
    except subprocess.CalledProcessError as e:
        print(f"Error fetching audit logs: {e}")
        return {}


def export_to_csv(member_roles, activity):
    """Export the results to a CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"iam_users_inactive_{PROJECT_ID}_{timestamp}.csv"
    
    print(f"\nGenerating report...")
    
    inactive_count = 0
    active_count = 0
    
    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['member', 'roles', 'last_seen', f'api_calls_last_{DAYS}_days', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Sort members for consistent output
        for member in sorted(member_roles.keys()):
            roles = ",".join(member_roles[member])
            
            # Extract email from member (remove user: prefix if present)
            email = member.replace("user:", "")
            
            if email in activity:
                last_seen = activity[email]["last_seen"]
                count = activity[email]["count"]
                status = "active"
                active_count += 1
            else:
                last_seen = "none"
                count = 0
                status = "inactive"
                inactive_count += 1
            
            writer.writerow({
                'member': email,
                'roles': roles,
                'last_seen': last_seen,
                f'api_calls_last_{DAYS}_days': count,
                'status': status
            })
    
    print(f"\n{'='*60}")
    print(f"Summary for project: {PROJECT_ID}")
    print(f"{'='*60}")
    print(f"Total human users: {len(member_roles)}")
    print(f"Active (last {DAYS} days): {active_count}")
    print(f"Inactive (last {DAYS} days): {inactive_count}")
    print(f"\n✓ Report exported to: {output_file}")


def main():
    """Main execution function."""
    print(f"\n{'='*60}")
    print(f"GCP IAM User Activity Report (Human Users Only)")
    print(f"Project: {PROJECT_ID}")
    print(f"Inactivity threshold: {DAYS} days")
    print(f"{'='*60}\n")
    
    # Get IAM members and their roles
    member_roles = get_iam_members()
    if not member_roles:
        print("No IAM members found or error occurred.")
        return
    
    # Get user activity from audit logs
    activity = get_user_activity()
    
    # Export results to CSV
    export_to_csv(member_roles, activity)


if __name__ == "__main__":
    main()
