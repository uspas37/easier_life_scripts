#!/usr/bin/env python3
"""
Script to delete unattached GCP disks from an input file.
Input file format: Each line contains "project_id disk_name" (space-separated).
"""

import argparse
import os
import sys
from google.cloud import compute_v1


def get_disk(project_id: str, disk_name: str) -> tuple[compute_v1.Disk | None, str | None, str | None]:
    """
    Retrieve disk information from GCP.
    Returns (disk, zone, error) - error is set if there was an API error.
    """
    try:
        disks_client = compute_v1.DisksClient()
        zones_client = compute_v1.ZonesClient()
        
        # Search across all zones for the disk
        for zone in zones_client.list(project=project_id):
            try:
                disk = disks_client.get(project=project_id, zone=zone.name, disk=disk_name)
                return disk, zone.name, None
            except Exception:
                continue
        
        return None, None, None
    except Exception as e:
        return None, None, str(e)


def is_disk_unattached(disk: compute_v1.Disk) -> bool:
    """Check if a disk is unattached (has no users)."""
    return not disk.users or len(disk.users) == 0


def delete_disk(project_id: str, zone: str, disk_name: str) -> bool:
    """Delete a disk from GCP. Returns True if successful."""
    disks_client = compute_v1.DisksClient()
    try:
        operation = disks_client.delete(project=project_id, zone=zone, disk=disk_name)
        # Wait for the operation to complete
        wait_for_operation(project_id, zone, operation.name)
        return True
    except Exception as e:
        print(f"  ERROR: Failed to delete disk: {e}")
        return False


def wait_for_operation(project_id: str, zone: str, operation_name: str):
    """Wait for a zone operation to complete."""
    zone_ops_client = compute_v1.ZoneOperationsClient()
    while True:
        result = zone_ops_client.get(project=project_id, zone=zone, operation=operation_name)
        if result.status == compute_v1.Operation.Status.DONE:
            if result.error:
                raise Exception(f"Operation failed: {result.error}")
            return result
        

def parse_input_file(file_path: str) -> list[tuple[str, str]]:
    """Parse input file and return list of (project_id, disk_name) tuples."""
    entries = []
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) < 2:
                print(f"WARNING: Skipping line {line_num} - invalid format: {line}")
                continue
            project_id, disk_name = parts[0], parts[1]
            entries.append((project_id, disk_name))
    return entries


def main():
    # Default input file is disks_list.csv in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_input_file = os.path.join(script_dir, 'disks_list.csv')
    
    parser = argparse.ArgumentParser(
        description='Delete unattached GCP disks from an input file.'
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default=default_input_file,
        help='Path to input file with "project_id disk_name" per line (default: disks_list.csv)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    args = parser.parse_args()

    entries = parse_input_file(args.input_file)
    if not entries:
        print("No valid entries found in input file.")
        sys.exit(1)

    print(f"Processing {len(entries)} disk(s)...\n")
    
    deleted_count = 0
    skipped_count = 0
    error_count = 0

    for project_id, disk_name in entries:
        print(f"Processing: {project_id} / {disk_name}")
        
        # Get disk info
        disk, zone, error = get_disk(project_id, disk_name)
        if error:
            print(f"  ERROR: {error}")
            error_count += 1
            continue
        if not disk:
            print(f"  SKIP: Disk not found in any zone")
            skipped_count += 1
            continue
        
        print(f"  Found in zone: {zone}")
        
        # Verify disk is unattached
        if not is_disk_unattached(disk):
            print(f"  SKIP: Disk is attached to: {', '.join(disk.users)}")
            skipped_count += 1
            continue
        
        print(f"  Status: Unattached (confirmed)")
        
        # Delete or dry-run
        if args.dry_run:
            print(f"  DRY-RUN: Would delete disk")
            deleted_count += 1
        else:
            if delete_disk(project_id, zone, disk_name):
                print(f"  DELETED: Successfully deleted disk")
                deleted_count += 1
            else:
                error_count += 1

    # Summary
    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  {'Would delete' if args.dry_run else 'Deleted'}: {deleted_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")


if __name__ == '__main__':
    main()
