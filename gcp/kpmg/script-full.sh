#!/bin/bash

# Output file
OUTPUT_FILE="results-full.csv"

# Add CSV header to the output file
echo "project_id,instance,zone,creationTimestamp,licenses" > "$OUTPUT_FILE"

# Get all GCP projects
projects=$(gcloud projects list --format="value(projectId)" | grep -v "sys-")

for project_id in $projects; do
    echo "Processing project: $project_id"

    # Check if Compute Engine API is enabled for the project
    if gcloud services list --project="$project_id" --filter="name:compute.googleapis.com" --format="value(state)" 2>/dev/null | grep -q "ENABLED"; then
        echo "  Compute Engine API is enabled."

        # List all compute instances in the project
        instances=$(gcloud compute instances list --project="$project_id" --format="json" 2>/dev/null)

        # Check if there are any instances
        if echo "$instances" | jq -e '.[]' >/dev/null; then
            # Iterate through each instance
            echo "$instances" | jq -c '.[]' | while read -r instance_data; do
                instance=$(echo "$instance_data" | jq -r '.name // empty')
                zone_full=$(echo "$instance_data" | jq -r '.zone // empty')
                zone=$(basename "$zone_full") # Extract just the zone name from the full URL

                # Get the operating system information
                os_family=$(echo "$instance_data" | jq -r '.disks[]?.licenses[]? | select(test("rhel|centos")) | . // empty')

                # Check if the OS is Red Hat (or CentOS which shares similar licensing often)
                if [[ "$os_family" == *"rhel"* || "$os_family" == *"centos"* ]]; then
                    echo "    Found Red Hat/CentOS instance: $instance in zone $zone"

                    # Describe the instance to get full details
                    instance_details=$(gcloud compute instances describe "$instance" --zone="$zone" --project="$project_id" --format="json" 2>/dev/null)

                    # Extract creationTimestamp
                    creationTimestamp=$(echo "$instance_details" | jq -r '.creationTimestamp // empty')

                    # Extract license information
                    licenses=$(echo "$instance_details" | jq -r '[.disks[]?.licenses[]?] | join(",") // empty')

                    # Output details to the CSV file
                    echo "$project_id,$instance,$zone,$creationTimestamp,\"$licenses\"" >> "$OUTPUT_FILE"
                fi
            done
        else
            echo "  No compute instances found in this project."
        fi
    else
        echo "  Compute Engine API is not enabled."
    fi
    echo "" # Add a blank line for readability between projects
done

echo "Script finished. Results are saved in $OUTPUT_FILE"
