#!/usr/bin/env python3
import csv
import subprocess
import json

def get_gcp_project_labels():
    """
    Fetches all GCP project IDs (excluding 'sys-' projects), their labels, and IAM users.
    Writes the data to a CSV file with one row per user per project.
    """
    output_file = 'gcp_project_users.csv'
    all_labels = set()
    rows = []

    try:
        # 1. Get a list of all GCP projects (excluding 'sys-' projects)
        print("Fetching project IDs...")
        project_list_cmd = "gcloud projects list --filter='NOT projectId:sys-*' --format=json"
        project_list_output = subprocess.check_output(project_list_cmd, shell=True, text=True)
        projects = json.loads(project_list_output)

        # 2. Iterate through each project to get its labels and users
        print(f"Fetching labels and users for {len(projects)} projects...")
        for idx, project in enumerate(projects, 1):
            project_id = project['projectId']
            labels = project.get('labels', {})
            
            # Collect all unique label keys to create CSV columns
            for label_key in labels.keys():
                all_labels.add(label_key)
            
            print(f"  [{idx}/{len(projects)}] Processing {project_id}...")
            
            # Fetch IAM users for this project
            try:
                iam_cmd = f"gcloud projects get-iam-policy {project_id} --format=json"
                iam_output = subprocess.check_output(iam_cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
                iam_policy = json.loads(iam_output)
                
                # Extract users (not service accounts, groups, or domains)
                users = set()
                if 'bindings' in iam_policy:
                    for binding in iam_policy['bindings']:
                        members = binding.get('members', [])
                        for member in members:
                            # Only include users (not service accounts)
                            if member.startswith('user:'):
                                user_email = member.replace('user:', '')
                                users.add(user_email)
                
                # Create a row for each user
                if users:
                    for user in sorted(users):
                        row = {
                            'project_id': project_id,
                            'user_email': user
                        }
                        row.update(labels)
                        rows.append(row)
                else:
                    # If no users found, still add a row with project info but empty user
                    row = {
                        'project_id': project_id,
                        'user_email': ''
                    }
                    row.update(labels)
                    rows.append(row)
                
            except subprocess.CalledProcessError:
                print(f"    ⚠️  Warning: Could not fetch IAM policy for {project_id}")
                row = {
                    'project_id': project_id,
                    'user_email': 'ERROR: No permissions'
                }
                row.update(labels)
                rows.append(row)
            except json.JSONDecodeError:
                print(f"    ⚠️  Warning: Could not parse IAM policy for {project_id}")
                row = {
                    'project_id': project_id,
                    'user_email': 'ERROR: Parse failed'
                }
                row.update(labels)
                rows.append(row)

    except subprocess.CalledProcessError as e:
        print(f"Error executing gcloud command: {e}")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON output from gcloud: {e}")
        return

    # 3. Write data to a CSV file
    if not all_labels:
        fieldnames = ['project_id', 'user_email']
    else:
        fieldnames = ['project_id', 'user_email'] + sorted(list(all_labels))

    try:
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in rows:
                writer.writerow(row)

        print(f"✅ Data successfully written to {output_file}")
        print(f"   Total rows: {len(rows)}")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    get_gcp_project_labels()
