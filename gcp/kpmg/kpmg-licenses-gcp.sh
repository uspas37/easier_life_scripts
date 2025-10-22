#!/bin/bash

# Define the input CSV file
INPUT_FILE="project-list.csv"

# Define the output CSV file
OUTPUT_FILE="results.csv"

# --- Script Start ---

echo "Starting script to gather gcloud instance details..."
echo "Input file: $INPUT_FILE"
echo "Output file: $OUTPUT_FILE"
echo "----------------------------------------------------"

# Create or clear the results.csv file and add a header
echo "project_id,instance,zone,creationTimestamp,licenses" > "$OUTPUT_FILE"
echo "Header added to $OUTPUT_FILE"

# Check if the input file exists
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: Input file '$INPUT_FILE' not found."
    echo "Please ensure 'project-list.csv' is in the same directory as the script."
    exit 1
fi

# Loop through each line in the input CSV file
# IFS=, sets the Internal Field Separator to a comma, so read -r can split by comma
# -r prevents backslash escapes from being interpreted
# Read instance, project_id, and zone from the CSV file
while IFS=',' read -r project_id instance zone; do
    # Skip empty lines
    if [[ -z "$instance" || -z "$project_id" || -z "$zone" ]]; then
        continue
    fi

    echo "Processing instance: $instance in project: $project_id in zone: $zone"

    # Fetch instance details in JSON format
    # 2>/dev/null suppresses error messages if the instance is not found or project is incorrect
    instance_details=$(gcloud compute instances describe "$instance" \
        --zone="$zone" \
        --project="$project_id" \
        --format="json" 2>/dev/null)

    # Initialize variables with default empty values
    creationTimestamp=""
    licenses=""

    # Check if instance_details is not empty (i.e., instance was found)
    if [[ -n "$instance_details" ]]; then
        # Extract creationTimestamp using jq
        # jq -r for raw output (no quotes)
        creationTimestamp=$(echo "$instance_details" | jq -r '.creationTimestamp // empty')

        # Extract licenses.
        # It iterates through disks, then licenses within each disk.
        # join(",") joins the array elements with a comma.
        # // empty ensures an empty string if no licenses are found or jq fails.
        licenses=$(echo "$instance_details" | jq -r '[.disks[]?.licenses[]?] | join(",") // empty')
    else
        echo "Warning: Instance '$instance' not found in project '$project_id' or access denied. Skipping."
        # If instance not found, creationTimestamp and licenses remain empty strings
    fi

    # Append the collected data to the results.csv file
    # Ensure all variables are quoted to handle spaces or special characters correctly
    echo "$project_id,$instance,$zone,$creationTimestamp,$licenses" >> "$OUTPUT_FILE"

done < "$INPUT_FILE"

echo "----------------------------------------------------"
echo "Script finished. Results are in $OUTPUT_FILE"
