#!/usr/bin/env python3
import csv
import subprocess
import json

def get_gcp_project_labels():
    """
    Fetches all GCP project IDs (excluding 'sys-' projects) and their labels,
    then writes the data to a CSV file.
    """
    output_file = 'gcp_project_labels.csv'
    all_labels = set()
    project_data = {}

    try:
        # 1. Get a list of all GCP projects (excluding 'sys-' projects)
        print("Fetching project IDs...")
        project_list_cmd = "gcloud projects list --filter='NOT projectId:sys-*' --format=json"
        project_list_output = subprocess.check_output(project_list_cmd, shell=True, text=True)
        projects = json.loads(project_list_output)

        # 2. Iterate through each project to get its labels
        print("Fetching labels for each project...")
        for project in projects:
            project_id = project['projectId']
            labels = project.get('labels', {})
            project_data[project_id] = labels
            
            # Collect all unique label keys to create CSV columns
            for label_key in labels.keys():
                all_labels.add(label_key)

    except subprocess.CalledProcessError as e:
        print(f"Error executing gcloud command: {e}")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON output from gcloud: {e}")
        return

    # 3. Write data to a CSV file
    if not all_labels:
        print("No labels found across any of the projects. Creating a CSV with only project IDs.")
        fieldnames = ['project_id']
    else:
        fieldnames = ['project_id'] + sorted(list(all_labels))

    try:
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for project_id, labels in project_data.items():
                row = {'project_id': project_id}
                row.update(labels)
                writer.writerow(row)

        print(f"✅ Data successfully written to {output_file}")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    get_gcp_project_labels()
