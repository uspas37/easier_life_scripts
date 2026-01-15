#!/usr/bin/env python3
"""
This script will fetch GCP project labels (owner, approver_1, approver_2, approver_3)
from a list of project numbers in an input file.

How to run it:

python3 project_labels_from_input.py
# Or specify custom input/output files:
python3 project_labels_from_input.py my_projects.txt -o results.csv

"""

import argparse
import csv
import json
import os
import subprocess
import sys


def get_project_labels(project_number: str) -> dict:
    """
    Fetch labels for a GCP project by project number.
    Returns dict with project_id, owner, approver_1, approver_2, approver_3.
    """
    try:
        cmd = f"gcloud projects describe {project_number} --format=json"
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        project = json.loads(output)
        
        project_id = project.get('projectId', project_number)
        labels = project.get('labels', {})
        
        return {
            'project_id': project_id,
            'owner': labels.get('owner', ''),
            'approver_1': labels.get('approver_1', ''),
            'approver_2': labels.get('approver_2', ''),
            'approver_3': labels.get('approver_3', ''),
        }
    except subprocess.CalledProcessError:
        print(f"  ERROR: Could not fetch project {project_number}")
        return {
            'project_id': project_number,
            'owner': 'ERROR',
            'approver_1': 'ERROR',
            'approver_2': 'ERROR',
            'approver_3': 'ERROR',
        }
    except json.JSONDecodeError:
        print(f"  ERROR: Invalid JSON response for project {project_number}")
        return {
            'project_id': project_number,
            'owner': 'ERROR',
            'approver_1': 'ERROR',
            'approver_2': 'ERROR',
            'approver_3': 'ERROR',
        }


def parse_input_file(file_path: str) -> list[str]:
    """Parse input file and return list of project numbers."""
    project_numbers = []
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            project_numbers.append(line)
    return project_numbers


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_input_file = os.path.join(script_dir, 'projects_input.txt')
    default_output_file = os.path.join(script_dir, 'project_labels_output.csv')
    
    parser = argparse.ArgumentParser(
        description='Fetch GCP project labels from a list of project numbers.'
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default=default_input_file,
        help='Path to input file with project numbers (one per line)'
    )
    parser.add_argument(
        '-o', '--output',
        default=default_output_file,
        help='Path to output CSV file (default: project_labels_output.csv)'
    )
    args = parser.parse_args()

    # Parse input file
    if not os.path.exists(args.input_file):
        print(f"ERROR: Input file not found: {args.input_file}")
        sys.exit(1)
    
    project_numbers = parse_input_file(args.input_file)
    if not project_numbers:
        print("No valid project numbers found in input file.")
        sys.exit(1)

    print(f"Processing {len(project_numbers)} project(s)...\n")
    
    results = []
    for project_number in project_numbers:
        print(f"Fetching labels for: {project_number}")
        labels = get_project_labels(project_number)
        print(f"  -> {labels['project_id']}: owner={labels['owner']}")
        results.append(labels)

    # Write to CSV
    fieldnames = ['project_id', 'owner', 'approver_1', 'approver_2', 'approver_3']
    with open(args.output, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Results written to {args.output}")
    print(f"   Total projects: {len(results)}")


if __name__ == '__main__':
    main()
