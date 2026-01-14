import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_gcloud(args):
    """Run a gcloud command and return (returncode, stdout, stderr)."""

    result = subprocess.run(
        ["gcloud", *args],
        text=True,
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr


def get_project_policy(project_id):
    """Return IAM policy for a project as dict, or None on error."""

    rc, out, err = run_gcloud([
        "projects",
        "get-iam-policy",
        project_id,
        "--format=json",
    ])
    if rc != 0:
        print(f"[ERROR] Failed to get IAM policy for project {project_id}: {err.strip()}", file=sys.stderr)
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Could not parse IAM policy JSON for project {project_id}: {e}", file=sys.stderr)
        return None


def find_roles_for_member(policy, member):
    """Return list of role strings for which member is present in bindings."""

    roles = []
    if not policy:
        return roles
    for binding in policy.get("bindings", []):
        members = binding.get("members", [])
        if member in members:
            role = binding.get("role")
            if role:
                roles.append(role)
    return roles


def remove_member_from_project_roles(project_id, member, roles, dry_run=False):
    """Remove member from given roles on the project."""

    for role in roles:
        print(f"[INFO] Removing {member} from role {role} on project {project_id} (dry_run={dry_run})")
        if dry_run:
            continue

        rc, out, err = run_gcloud([
            "projects",
            "remove-iam-policy-binding",
            project_id,
            "--member",
            member,
            "--role",
            role,
            "--quiet",
        ])

        if rc != 0:
            print(
                f"[ERROR] Failed to remove {member} from role {role} on project {project_id}: {err.strip()}",
                file=sys.stderr,
            )
        else:
            print(f"[OK] Removed {member} from role {role} on project {project_id}")


def process_input_file(path, dry_run=False):
    """Read project/user pairs from file and process each."""

    input_path = Path(path)
    if not input_path.is_file():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        return 1

    with input_path.open() as f:
        lines = f.readlines()

    if not lines:
        print(f"[WARN] Input file {input_path} is empty")
        return 0

    exit_code = 0

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 2:
            print(f"[WARN] Line {lineno}: expected 'PROJECT_ID USER_EMAIL', got: {raw_line!r}", file=sys.stderr)
            exit_code = 1
            continue

        project_id, user_email = parts[0], parts[1]
        member = f"user:{user_email}"
        print(f"\n[INFO] Processing project={project_id}, user={user_email} (line {lineno})")

        policy = get_project_policy(project_id)
        if policy is None:
            exit_code = 1
            continue

        roles = find_roles_for_member(policy, member)
        if not roles:
            print(f"[INFO] User {member} not found in IAM policy for project {project_id}, nothing to remove")
            continue

        print(f"[INFO] User {member} found in roles: {', '.join(roles)}")
        remove_member_from_project_roles(project_id, member, roles, dry_run=dry_run)

    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove IAM users from GCP projects based on an input file.")
    parser.add_argument(
        "--input",
        "-i",
        default="input_users.txt",
        help="Path to input file with 'PROJECT_ID USER_EMAIL' per line (default: input_users.txt)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be removed, without calling gcloud to change IAM.",
    )

    args = parser.parse_args(argv)

    rc = process_input_file(args.input, dry_run=args.dry_run)
    sys.exit(rc)


if __name__ == "__main__":
    main()

