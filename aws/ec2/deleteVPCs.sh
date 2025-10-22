#/usr/bin/env bash

export REGIONS=$(aws ec2 describe-regions | jq -r ".Regions[].RegionName")

echo "Below VPCs will be deleted...Please be careful"
sleep 5
for region in $REGIONS; do
        echo $region
        aws --region=$region ec2 describe-vpcs | jq ".Vpcs[]|{is_default: .IsDefault, cidr: .CidrBlock, id: .VpcId} | select(.is_default)"
done

read -p "Are you sure? y/n " -n 1 -r
echo 
if [[ $REPLY =~ ^[Yy]$ ]]
then
        for region in $REGIONS; do
                echo "Region =  $region"
                export IDs=$(aws --region=$region ec2 describe-vpcs | jq -r ".Vpcs[]|{is_default: .IsDefault, id: .VpcId} | select(.is_default) | .id")
                for id in "$IDs" ; do
                        if [ -z "$id" ]; then
                                continue
                        fi

                        # Delete IGWs
                        for igw in `aws --region=$region ec2 describe-internet-gateways | jq -r ".InternetGateways[] | {id: .InternetGatewayId, vpc: .Attachments[0].VpcId} | select(.vpc == \"$id\") | .id"` ; do
                                echo "Deleting Internet Gateway"
                                echo "$region $id $igw"
                                aws --region=$region ec2 detach-internet-gateway --internet-gateway-id=$igw --vpc-id=$id
                                aws --region=$region ec2 delete-internet-gateway --internet-gateway-id=$igw
                        done

                        # Delete Subnets
                        for sub in `aws --region=$region ec2 describe-subnets | jq -r ".Subnets[] | {id: .SubnetId, vpc: .VpcId} | select(.vpc == \"$id\") | .id"` ; do
                                echo "Deleting Subnet" 
                                echo "$region $id $sub"
                                aws --region=$region ec2 delete-subnet --subnet-id=$sub
                        done

                        echo "Deleting VPC"
                        echo "$region $id"
                        aws --region=$region ec2 delete-vpc --vpc-id=$id
                done
        done
fi