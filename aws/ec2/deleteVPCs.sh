#!/usr/bin/env bash
set -euo pipefail

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Please install jq first."
    exit 1
fi

export REGIONS=$(aws ec2 describe-regions | jq -r ".Regions[].RegionName")

echo "========================================"
echo "DEFAULT VPCs TO BE DELETED"
echo "========================================"
echo "WARNING: This will delete DEFAULT VPCs only!"
echo "Please review carefully before proceeding."
echo "========================================"
sleep 3

for region in $REGIONS; do
        echo ""
        echo "Region: $region"
        aws --region=$region ec2 describe-vpcs | jq ".Vpcs[]|{is_default: .IsDefault, cidr: .CidrBlock, id: .VpcId} | select(.is_default)"
done

echo ""
echo "========================================"

read -p "Are you sure? y/n " -n 1 -r
echo 
if [[ $REPLY =~ ^[Yy]$ ]]
then
        for region in $REGIONS; do
                echo ""
                echo "========================================"
                echo "Processing Region: $region"
                echo "========================================"
                export IDs=$(aws --region=$region ec2 describe-vpcs | jq -r ".Vpcs[]|{is_default: .IsDefault, id: .VpcId} | select(.is_default) | .id")
                
                # Fix: Remove quotes to iterate properly
                for id in $IDs ; do
                        if [ -z "$id" ]; then
                                echo "No default VPCs found in $region"
                                continue
                        fi

                        echo "Processing VPC: $id"
                        
                        # Delete NAT Gateways first (they depend on subnets)
                        echo "  Checking for NAT Gateways..."
                        for nat in $(aws --region=$region ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$id" "Name=state,Values=available,pending" | jq -r ".NatGateways[].NatGatewayId") ; do
                                echo "  Deleting NAT Gateway: $nat"
                                aws --region=$region ec2 delete-nat-gateway --nat-gateway-id=$nat 2>/dev/null || echo "    Failed to delete NAT Gateway $nat"
                        done
                        
                        # Wait for NAT Gateways to delete
                        echo "  Waiting for NAT Gateways to delete..."
                        sleep 10
                        
                        # Delete VPC Endpoints
                        echo "  Checking for VPC Endpoints..."
                        for endpoint in $(aws --region=$region ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$id" | jq -r ".VpcEndpoints[].VpcEndpointId") ; do
                                echo "  Deleting VPC Endpoint: $endpoint"
                                aws --region=$region ec2 delete-vpc-endpoints --vpc-endpoint-ids $endpoint 2>/dev/null || echo "    Failed to delete endpoint $endpoint"
                        done

                        # Delete IGWs
                        echo "  Checking for Internet Gateways..."
                        for igw in $(aws --region=$region ec2 describe-internet-gateways | jq -r ".InternetGateways[] | {id: .InternetGatewayId, vpc: .Attachments[0].VpcId} | select(.vpc == \"$id\") | .id") ; do
                                echo "  Detaching and deleting Internet Gateway: $igw"
                                aws --region=$region ec2 detach-internet-gateway --internet-gateway-id=$igw --vpc-id=$id 2>/dev/null || echo "    Failed to detach IGW $igw"
                                aws --region=$region ec2 delete-internet-gateway --internet-gateway-id=$igw 2>/dev/null || echo "    Failed to delete IGW $igw"
                        done

                        # Delete Subnets
                        echo "  Checking for Subnets..."
                        for sub in $(aws --region=$region ec2 describe-subnets | jq -r ".Subnets[] | {id: .SubnetId, vpc: .VpcId} | select(.vpc == \"$id\") | .id") ; do
                                echo "  Deleting Subnet: $sub"
                                aws --region=$region ec2 delete-subnet --subnet-id=$sub 2>/dev/null || echo "    Failed to delete subnet $sub"
                        done
                        
                        # Delete custom route tables (main route table is deleted with VPC)
                        echo "  Checking for Route Tables..."
                        for rt in $(aws --region=$region ec2 describe-route-tables --filters "Name=vpc-id,Values=$id" | jq -r ".RouteTables[] | select(.Associations[].Main != true) | .RouteTableId") ; do
                                echo "  Deleting Route Table: $rt"
                                aws --region=$region ec2 delete-route-table --route-table-id=$rt 2>/dev/null || echo "    Failed to delete route table $rt"
                        done
                        
                        # Delete custom Network ACLs (default ACL is deleted with VPC)
                        echo "  Checking for Network ACLs..."
                        for acl in $(aws --region=$region ec2 describe-network-acls --filters "Name=vpc-id,Values=$id" | jq -r ".NetworkAcls[] | select(.IsDefault != true) | .NetworkAclId") ; do
                                echo "  Deleting Network ACL: $acl"
                                aws --region=$region ec2 delete-network-acl --network-acl-id=$acl 2>/dev/null || echo "    Failed to delete ACL $acl"
                        done
                        
                        # Delete custom Security Groups (default SG is deleted with VPC)
                        echo "  Checking for Security Groups..."
                        for sg in $(aws --region=$region ec2 describe-security-groups --filters "Name=vpc-id,Values=$id" | jq -r ".SecurityGroups[] | select(.GroupName != \"default\") | .GroupId") ; do
                                echo "  Deleting Security Group: $sg"
                                aws --region=$region ec2 delete-security-group --group-id=$sg 2>/dev/null || echo "    Failed to delete SG $sg"
                        done

                        # Finally, delete the VPC
                        echo "  Deleting VPC: $id"
                        if aws --region=$region ec2 delete-vpc --vpc-id=$id 2>/dev/null; then
                                echo "  ✓ Successfully deleted VPC $id in $region"
                        else
                                echo "  ✗ Failed to delete VPC $id in $region"
                                echo "    There may be remaining dependencies. Check the AWS console."
                        fi
                        echo ""
                done
        done
        
        echo ""
        echo "========================================"
        echo "Deletion process completed!"
        echo "========================================"
fi