#!/bin/bash
set -euo pipefail

# Script to check VPC and Subnet usage in the current AWS account and region
# Determines if VPCs and Subnets have active resources

# Get current AWS account and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
REGION=${REGION:-us-east-1}

echo "=========================================="
echo "AWS VPC and Subnet Usage Report"
echo "=========================================="
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Timestamp: $(date)"
echo "=========================================="
echo ""

# Output CSV file
OUTPUT_FILE="vpc_usage_${ACCOUNT_ID}_${REGION}_$(date +%Y%m%d_%H%M%S).csv"

# Function to check if a VPC is in use
check_vpc_usage() {
    local vpc_id=$1
    local vpc_name=$2
    local is_default=$3
    
    # Check for EC2 instances
    local ec2_count=$(aws ec2 describe-instances \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query 'Reservations[*].Instances[*].InstanceId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for RDS instances
    local rds_count=$(aws rds describe-db-instances \
        --query "DBInstances[?DBSubnetGroup.VpcId=='$vpc_id'].DBInstanceIdentifier" \
        --region "$REGION" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for Lambda functions (via ENIs)
    local lambda_eni_count=$(aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=interface-type,Values=lambda" \
        --query 'NetworkInterfaces[*].NetworkInterfaceId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for ELBs (Classic)
    local elb_count=$(aws elb describe-load-balancers \
        --query "LoadBalancerDescriptions[?VPCId=='$vpc_id'].LoadBalancerName" \
        --region "$REGION" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for ALB/NLB
    local alb_count=$(aws elbv2 describe-load-balancers \
        --query "LoadBalancers[?VpcId=='$vpc_id'].LoadBalancerArn" \
        --region "$REGION" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for NAT Gateways
    local nat_count=$(aws ec2 describe-nat-gateways \
        --filter "Name=vpc-id,Values=$vpc_id" "Name=state,Values=pending,available" \
        --query 'NatGateways[*].NatGatewayId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for VPC Endpoints
    local endpoint_count=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=$vpc_id" \
        --query 'VpcEndpoints[*].VpcEndpointId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for Transit Gateway Attachments
    local tgw_count=$(aws ec2 describe-transit-gateway-vpc-attachments \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=state,Values=available,pending" \
        --query 'TransitGatewayVpcAttachments[*].TransitGatewayAttachmentId' \
        --region "$REGION" \
        --output text 2>/dev/null | wc -w | tr -d ' ' || echo "0")
    
    # Check for VPN Gateways
    local vpn_count=$(aws ec2 describe-vpn-gateways \
        --filters "Name=attachment.vpc-id,Values=$vpc_id" "Name=state,Values=available" \
        --query 'VpnGateways[*].VpnGatewayId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for Network Interfaces (excluding Lambda)
    local eni_count=$(aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$vpc_id" \
        --query 'NetworkInterfaces[?InterfaceType!=`lambda`].NetworkInterfaceId' \
        --region "$REGION" \
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
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Output to CSV
    echo "$vpc_id,\"$vpc_name\",$is_default,$status,$total_resources,$subnet_count,$ec2_count,$rds_count,$lambda_eni_count,$elb_count,$alb_count,$nat_count,$endpoint_count,$tgw_count,$vpn_count,$eni_count"
}

# Function to check subnet usage
check_subnet_usage() {
    local subnet_id=$1
    local subnet_name=$2
    local vpc_id=$3
    local cidr=$4
    local az=$5
    
    # Check for EC2 instances in subnet
    local ec2_count=$(aws ec2 describe-instances \
        --filters "Name=subnet-id,Values=$subnet_id" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query 'Reservations[*].Instances[*].InstanceId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for Network Interfaces in subnet
    local eni_count=$(aws ec2 describe-network-interfaces \
        --filters "Name=subnet-id,Values=$subnet_id" \
        --query 'NetworkInterfaces[*].NetworkInterfaceId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Check for NAT Gateways in subnet
    local nat_count=$(aws ec2 describe-nat-gateways \
        --filter "Name=subnet-id,Values=$subnet_id" "Name=state,Values=pending,available" \
        --query 'NatGateways[*].NatGatewayId' \
        --region "$REGION" \
        --output text | wc -w | tr -d ' ')
    
    # Get available IPs
    local available_ips=$(aws ec2 describe-subnets \
        --subnet-ids "$subnet_id" \
        --query 'Subnets[0].AvailableIpAddressCount' \
        --region "$REGION" \
        --output text)
    
    # Determine usage status
    local status="UNUSED"
    local total_resources=$((ec2_count + eni_count + nat_count))
    if [ $total_resources -gt 0 ]; then
        status="IN USE"
    fi
    
    echo "$subnet_id,\"$subnet_name\",$vpc_id,$cidr,$az,$status,$total_resources,$ec2_count,$eni_count,$nat_count,$available_ips"
}

echo "Analyzing VPCs and Subnets..."
echo ""

# Create VPC report
VPC_FILE="vpc_report_${ACCOUNT_ID}_${REGION}_$(date +%Y%m%d_%H%M%S).csv"
echo "vpc_id,vpc_name,is_default,status,total_resources,subnet_count,ec2_instances,rds_instances,lambda_enis,classic_elbs,alb_nlb,nat_gateways,vpc_endpoints,tgw_attachments,vpn_gateways,network_interfaces" > "$VPC_FILE"

# Get all VPCs
vpc_list=$(aws ec2 describe-vpcs --region "$REGION" --query 'Vpcs[*].[VpcId,IsDefault]' --output text)

vpc_count=0
unused_vpc_count=0

# Store VPC data for table display
declare -a vpc_table_data

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
    
    echo "Checking VPC: $vpc_id ($vpc_name)..."
    
    # Check VPC usage and append to file
    vpc_data=$(check_vpc_usage "$vpc_id" "$vpc_name" "$is_default")
    echo "$vpc_data" >> "$VPC_FILE"
    
    # Store for table display
    vpc_table_data+=("$vpc_data")
    
    # Count unused VPCs
    if echo "$vpc_data" | grep -q "UNUSED"; then
        ((unused_vpc_count++))
    fi
    
    ((vpc_count++))
done <<< "$vpc_list"

echo ""
echo "VPC analysis complete!"
echo ""

# Display VPC results in table format
echo "=========================================================================================================="
echo "VPC USAGE REPORT"
echo "=========================================================================================================="
printf "%-21s %-25s %-8s %-8s %-10s %-8s\n" "VPC ID" "Name" "Default" "Status" "Resources" "Subnets"
echo "----------------------------------------------------------------------------------------------------------"

for vpc_row in "${vpc_table_data[@]}"; do
    IFS=',' read -r vpc_id vpc_name is_default status total_resources subnet_count rest <<< "$vpc_row"
    # Remove quotes from name
    vpc_name=$(echo "$vpc_name" | tr -d '"')
    # Truncate name if too long
    if [ ${#vpc_name} -gt 25 ]; then
        vpc_name="${vpc_name:0:22}..."
    fi
    printf "%-21s %-25s %-8s %-8s %-10s %-8s\n" "$vpc_id" "$vpc_name" "$is_default" "$status" "$total_resources" "$subnet_count"
done

echo "=========================================================================================================="
echo ""

# Create Subnet report
SUBNET_FILE="subnet_report_${ACCOUNT_ID}_${REGION}_$(date +%Y%m%d_%H%M%S).csv"
echo "subnet_id,subnet_name,vpc_id,cidr_block,availability_zone,status,total_resources,ec2_instances,network_interfaces,nat_gateways,available_ips" > "$SUBNET_FILE"

echo "Analyzing Subnets..."
echo ""

# Get all subnets
subnet_list=$(aws ec2 describe-subnets --region "$REGION" --query 'Subnets[*].[SubnetId,VpcId,CidrBlock,AvailabilityZone]' --output text)

subnet_count=0
unused_subnet_count=0

# Store subnet data for table display
declare -a subnet_table_data

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
    subnet_data=$(check_subnet_usage "$subnet_id" "$subnet_name" "$vpc_id" "$cidr" "$az")
    echo "$subnet_data" >> "$SUBNET_FILE"
    
    # Store for table display
    subnet_table_data+=("$subnet_data")
    
    # Count unused subnets
    if echo "$subnet_data" | grep -q "UNUSED"; then
        ((unused_subnet_count++))
    fi
    
    ((subnet_count++))
done <<< "$subnet_list"

echo ""

# Display Subnet results in table format
echo "=========================================================================================================="
echo "SUBNET USAGE REPORT"
echo "=========================================================================================================="
printf "%-24s %-25s %-18s %-15s %-8s %-10s\n" "Subnet ID" "Name" "CIDR Block" "AZ" "Status" "Resources"
echo "----------------------------------------------------------------------------------------------------------"

for subnet_row in "${subnet_table_data[@]}"; do
    IFS=',' read -r subnet_id subnet_name vpc_id cidr az status total_resources rest <<< "$subnet_row"
    # Remove quotes from name
    subnet_name=$(echo "$subnet_name" | tr -d '"')
    # Truncate name if too long
    if [ ${#subnet_name} -gt 25 ]; then
        subnet_name="${subnet_name:0:22}..."
    fi
    printf "%-24s %-25s %-18s %-15s %-8s %-10s\n" "$subnet_id" "$subnet_name" "$cidr" "$az" "$status" "$total_resources"
done

echo "=========================================================================================================="
echo ""

# Summary
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo "Total VPCs: $vpc_count"
echo "  - In use: $((vpc_count - unused_vpc_count))"
echo "  - Unused: $unused_vpc_count"
echo ""
echo "Total Subnets: $subnet_count"
echo "  - In use: $((subnet_count - unused_subnet_count))"
echo "  - Unused: $unused_subnet_count"
echo ""
echo "Detailed Reports:"
echo "  ✓ VPC report: $VPC_FILE"
echo "  ✓ Subnet report: $SUBNET_FILE"
echo "=========================================="