#!/bin/bash
set -euo pipefail

# Script to check VPC and Subnet usage across all AWS regions in the current account
# Determines if VPCs and Subnets have active resources

# Get current AWS account
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Get all enabled regions
echo "Fetching all enabled AWS regions..."
REGIONS=$(aws ec2 describe-regions --query 'Regions[*].RegionName' --output text)

echo "=========================================="
echo "AWS VPC and Subnet Usage Report (Global)"
echo "=========================================="
echo "Account ID: $ACCOUNT_ID"
echo "Regions: All enabled regions"
echo "Timestamp: $(date)"
echo "=========================================="
echo ""

# Output CSV files with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
VPC_FILE="vpc_report_${ACCOUNT_ID}_global_${TIMESTAMP}.csv"
SUBNET_FILE="subnet_report_${ACCOUNT_ID}_global_${TIMESTAMP}.csv"

# Function to check if a VPC is in use
check_vpc_usage() {
    local vpc_id=$1
    local vpc_name=$2
    local is_default=$3
    local region=$4
    
    # Check for EC2 instances
    local ec2_count=$(aws ec2 describe-instances \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query 'Reservations[*].Instances[*].InstanceId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for RDS instances
    local rds_count=$(aws rds describe-db-instances \
        --query "DBInstances[?DBSubnetGroup.VpcId=='$vpc_id'].DBInstanceIdentifier" \
        --region "$region" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for Lambda functions (via ENIs)
    local lambda_eni_count=$(aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=interface-type,Values=lambda" \
        --query 'NetworkInterfaces[*].NetworkInterfaceId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for ELBs (Classic)
    local elb_count=$(aws elb describe-load-balancers \
        --query "LoadBalancerDescriptions[?VPCId=='$vpc_id'].LoadBalancerName" \
        --region "$region" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for ALB/NLB
    local alb_count=$(aws elbv2 describe-load-balancers \
        --query "LoadBalancers[?VpcId=='$vpc_id'].LoadBalancerArn" \
        --region "$region" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for NAT Gateways
    local nat_count=$(aws ec2 describe-nat-gateways \
        --filter "Name=vpc-id,Values=$vpc_id" "Name=state,Values=pending,available" \
        --query 'NatGateways[*].NatGatewayId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for VPC Endpoints
    local endpoint_count=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=$vpc_id" \
        --query 'VpcEndpoints[*].VpcEndpointId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for Transit Gateway Attachments
    local tgw_count=$(aws ec2 describe-transit-gateway-vpc-attachments \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=state,Values=available,pending" \
        --query 'TransitGatewayVpcAttachments[*].TransitGatewayAttachmentId' \
        --region "$region" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for VPN Gateways
    local vpn_count=$(aws ec2 describe-vpn-gateways \
        --filters "Name=attachment.vpc-id,Values=$vpc_id" "Name=state,Values=available" \
        --query 'VpnGateways[*].VpnGatewayId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for Network Interfaces (excluding Lambda)
    local eni_count=$(aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$vpc_id" \
        --query 'NetworkInterfaces[?InterfaceType!=`lambda`].NetworkInterfaceId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Calculate total resources
    local total_resources=$((ec2_count + rds_count + lambda_eni_count + elb_count + alb_count + nat_count + endpoint_count + tgw_count + vpn_count))
    
    # Determine usage status
    local status="UNUSED"
    if [ $total_resources -gt 0 ]; then
        status="IN USE"
    fi
    
    # Get subnet count
    local subnet_count=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$vpc_id" \
        --query 'Subnets[*].SubnetId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Output to CSV (including region)
    echo "$region,$vpc_id,\"$vpc_name\",$is_default,$status,$total_resources,$subnet_count,$ec2_count,$rds_count,$lambda_eni_count,$elb_count,$alb_count,$nat_count,$endpoint_count,$tgw_count,$vpn_count,$eni_count"
}

# Function to check subnet usage
check_subnet_usage() {
    local subnet_id=$1
    local subnet_name=$2
    local vpc_id=$3
    local cidr=$4
    local az=$5
    local region=$6
    
    # Check for EC2 instances in subnet
    local ec2_count=$(aws ec2 describe-instances \
        --filters "Name=subnet-id,Values=$subnet_id" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query 'Reservations[*].Instances[*].InstanceId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for Network Interfaces in subnet
    local eni_count=$(aws ec2 describe-network-interfaces \
        --filters "Name=subnet-id,Values=$subnet_id" \
        --query 'NetworkInterfaces[*].NetworkInterfaceId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Check for NAT Gateways in subnet
    local nat_count=$(aws ec2 describe-nat-gateways \
        --filter "Name=subnet-id,Values=$subnet_id" "Name=state,Values=pending,available" \
        --query 'NatGateways[*].NatGatewayId' \
        --region "$region" \
        --output text | wc -w | tr -d ' ')
    
    # Get available IPs
    local available_ips=$(aws ec2 describe-subnets \
        --subnet-ids "$subnet_id" \
        --query 'Subnets[0].AvailableIpAddressCount' \
        --region "$region" \
        --output text)
    
    # Determine usage status
    local status="UNUSED"
    local total_resources=$((ec2_count + eni_count + nat_count))
    if [ $total_resources -gt 0 ]; then
        status="IN USE"
    fi
    
    echo "$region,$subnet_id,\"$subnet_name\",$vpc_id,$cidr,$az,$status,$total_resources,$ec2_count,$eni_count,$nat_count,$available_ips"
}

# Initialize CSV files with headers
echo "region,vpc_id,vpc_name,is_default,status,total_resources,subnet_count,ec2_instances,rds_instances,lambda_enis,classic_elbs,alb_nlb,nat_gateways,vpc_endpoints,tgw_attachments,vpn_gateways,network_interfaces" > "$VPC_FILE"
echo "region,subnet_id,subnet_name,vpc_id,cidr_block,availability_zone,status,total_resources,ec2_instances,network_interfaces,nat_gateways,available_ips" > "$SUBNET_FILE"

# Initialize counters
total_vpc_count=0
total_unused_vpc_count=0
total_subnet_count=0
total_unused_subnet_count=0

# Store data for table display
declare -a vpc_table_data
declare -a subnet_table_data

# Store regional summary data
declare -A region_vpc_counts
declare -A region_vpc_used_counts
declare -A region_subnet_counts
declare -A region_subnet_used_counts

echo "Analyzing VPCs and Subnets across all regions..."
echo ""

# Loop through each region
for REGION in $REGIONS; do
    echo "=========================================="
    echo "Processing Region: $REGION"
    echo "=========================================="
    
    # Get all VPCs in this region
    vpc_list=$(aws ec2 describe-vpcs --region "$REGION" --query 'Vpcs[*].[VpcId,IsDefault]' --output text 2>/dev/null)
    
    # Skip if no VPCs or region is not accessible
    if [ -z "$vpc_list" ]; then
        echo "No VPCs found or region not accessible. Skipping..."
        echo ""
        continue
    fi
    
    region_vpc_count=0
    region_unused_vpc_count=0
    
    while IFS=$'\t' read -r vpc_id is_default; do
        # Get VPC name from tags
        vpc_name=$(aws ec2 describe-vpcs \
            --vpc-ids "$vpc_id" \
            --query 'Vpcs[0].Tags[?Key==`Name`].Value' \
            --region "$REGION" \
            --output text)
        
        if [ -z "$vpc_name" ]; then
            vpc_name="(no name)"
        fi
        
        echo "  Checking VPC: $vpc_id ($vpc_name)..."
        
        # Check VPC usage and append to file
        vpc_data=$(check_vpc_usage "$vpc_id" "$vpc_name" "$is_default" "$REGION")
        echo "$vpc_data" >> "$VPC_FILE"
        
        # Store for table display
        vpc_table_data+=("$vpc_data")
        
        # Count unused VPCs
        if echo "$vpc_data" | grep -q "UNUSED"; then
            ((region_unused_vpc_count++))
            ((total_unused_vpc_count++))
        fi
        
        ((region_vpc_count++))
        ((total_vpc_count++))
    done <<< "$vpc_list"
    
    echo "  Region $REGION: Found $region_vpc_count VPCs ($region_unused_vpc_count unused)"
    
    # Store regional VPC stats
    region_vpc_counts[$REGION]=$region_vpc_count
    region_vpc_used_counts[$REGION]=$((region_vpc_count - region_unused_vpc_count))
    
    # Get all subnets in this region
    subnet_list=$(aws ec2 describe-subnets --region "$REGION" --query 'Subnets[*].[SubnetId,VpcId,CidrBlock,AvailabilityZone]' --output text 2>/dev/null)
    
    region_subnet_count=0
    region_unused_subnet_count=0
    
    if [ -n "$subnet_list" ]; then
        while IFS=$'\t' read -r subnet_id vpc_id cidr az; do
            # Get subnet name from tags
            subnet_name=$(aws ec2 describe-subnets \
                --subnet-ids "$subnet_id" \
                --query 'Subnets[0].Tags[?Key==`Name`].Value' \
                --region "$REGION" \
                --output text)
            
            if [ -z "$subnet_name" ]; then
                subnet_name="(no name)"
            fi
            
            # Check subnet usage and append to file
            subnet_data=$(check_subnet_usage "$subnet_id" "$subnet_name" "$vpc_id" "$cidr" "$az" "$REGION")
            echo "$subnet_data" >> "$SUBNET_FILE"
            
            # Store for table display
            subnet_table_data+=("$subnet_data")
            
            # Count unused subnets
            if echo "$subnet_data" | grep -q "UNUSED"; then
                ((region_unused_subnet_count++))
                ((total_unused_subnet_count++))
            fi
            
            ((region_subnet_count++))
            ((total_subnet_count++))
        done <<< "$subnet_list"
    fi
    
    # Store regional Subnet stats
    region_subnet_counts[$REGION]=$region_subnet_count
    region_subnet_used_counts[$REGION]=$((region_subnet_count - region_unused_subnet_count))
    
    echo "  Region $REGION: Found $region_subnet_count Subnets ($region_unused_subnet_count unused)"
    echo ""
done

echo ""
echo "Analysis complete across all regions!"
echo ""

# Display VPC results in table format
echo "=========================================================================================================="
echo "VPC USAGE REPORT (Global)"
echo "=========================================================================================================="
printf "%-15s %-21s %-25s %-8s %-8s %-10s\n" "Region" "VPC ID" "Name" "Default" "Status" "Resources"
echo "----------------------------------------------------------------------------------------------------------"

for vpc_row in "${vpc_table_data[@]}"; do
    IFS=',' read -r region vpc_id vpc_name is_default status total_resources subnet_count rest <<< "$vpc_row"
    # Remove quotes from name
    vpc_name=$(echo "$vpc_name" | tr -d '"')
    # Truncate name if too long
    if [ ${#vpc_name} -gt 25 ]; then
        vpc_name="${vpc_name:0:22}..."
    fi
    printf "%-15s %-21s %-25s %-8s %-8s %-10s\n" "$region" "$vpc_id" "$vpc_name" "$is_default" "$status" "$total_resources"
done

echo "=========================================================================================================="
echo ""

# Display Subnet results in table format
echo "=========================================================================================================="
echo "SUBNET USAGE REPORT (Global)"
echo "=========================================================================================================="
printf "%-15s %-24s %-20s %-18s %-8s %-10s\n" "Region" "Subnet ID" "Name" "CIDR Block" "Status" "Resources"
echo "----------------------------------------------------------------------------------------------------------"

for subnet_row in "${subnet_table_data[@]}"; do
    IFS=',' read -r region subnet_id subnet_name vpc_id cidr az status total_resources rest <<< "$subnet_row"
    # Remove quotes from name
    subnet_name=$(echo "$subnet_name" | tr -d '"')
    # Truncate name if too long
    if [ ${#subnet_name} -gt 20 ]; then
        subnet_name="${subnet_name:0:17}..."
    fi
    printf "%-15s %-24s %-20s %-18s %-8s %-10s\n" "$region" "$subnet_id" "$subnet_name" "$cidr" "$status" "$total_resources"
done

echo "=========================================================================================================="
echo ""

# Summary Table by Region
echo "=========================================================================================================="
echo "REGIONAL SUMMARY TABLE"
echo "=========================================================================================================="
printf "%-20s | %-12s | %-12s | %-14s | %-14s\n" "Region" "Total VPCs" "VPCs In Use" "Total Subnets" "Subnets In Use"
echo "----------------------------------------------------------------------------------------------------------"

# Sort regions alphabetically and display stats
for REGION in $(echo "$REGIONS" | tr ' ' '\n' | sort); do
    vpc_total=${region_vpc_counts[$REGION]:-0}
    vpc_used=${region_vpc_used_counts[$REGION]:-0}
    subnet_total=${region_subnet_counts[$REGION]:-0}
    subnet_used=${region_subnet_used_counts[$REGION]:-0}
    
    # Only show regions that have VPCs or Subnets
    if [ $vpc_total -gt 0 ] || [ $subnet_total -gt 0 ]; then
        printf "%-20s | %-12s | %-12s | %-14s | %-14s\n" "$REGION" "$vpc_total" "$vpc_used" "$subnet_total" "$subnet_used"
    fi
done

echo "----------------------------------------------------------------------------------------------------------"
printf "%-20s | %-12s | %-12s | %-14s | %-14s\n" "TOTAL (All Regions)" "$total_vpc_count" "$((total_vpc_count - total_unused_vpc_count))" "$total_subnet_count" "$((total_subnet_count - total_unused_subnet_count))"
echo "=========================================================================================================="
echo ""

# Global Summary
echo "=========================================="
echo "GLOBAL SUMMARY"
echo "=========================================="
echo "Total VPCs (all regions): $total_vpc_count"
echo "  - In use: $((total_vpc_count - total_unused_vpc_count))"
echo "  - Unused: $total_unused_vpc_count"
echo ""
echo "Total Subnets (all regions): $total_subnet_count"
echo "  - In use: $((total_subnet_count - total_unused_subnet_count))"
echo "  - Unused: $total_unused_subnet_count"
echo ""
echo "Detailed Reports:"
echo "  ✓ VPC report: $VPC_FILE"
echo "  ✓ Subnet report: $SUBNET_FILE"
echo "=========================================="