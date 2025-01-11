#!/usr/bin/env python3
import boto3
import json
import time
import sys
from botocore.exceptions import ClientError

# Configuration
PROJECT_NAME = "jrw-chat-app"
AWS_REGION = "us-east-1"
DOMAIN_NAME = f"{PROJECT_NAME}-search"
INSTANCE_TYPE = "t3.small.search"  # Smallest instance type for dev/testing

def create_opensearch_domain(client, vpc_id, subnet_id, security_group_id):
    """Create OpenSearch domain with appropriate settings"""
    try:
        # Define cluster configuration
        cluster_config = {
            'InstanceType': INSTANCE_TYPE,
            'InstanceCount': 1,
            'DedicatedMasterEnabled': False,
            'ZoneAwarenessEnabled': False,
            'WarmEnabled': False,
        }

        # Define VPC options
        vpc_options = {
            'SubnetIds': [subnet_id],
            'SecurityGroupIds': [security_group_id]
        }

        # Define encryption settings
        encryption_at_rest = {
            'Enabled': True
        }

        # Define access policies
        access_policies = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": "*"  # Will be restricted by VPC and security group
                    },
                    "Action": "es:*",
                    "Resource": f"arn:aws:es:{AWS_REGION}:{boto3.client('sts').get_caller_identity()['Account']}:domain/{DOMAIN_NAME}/*"
                }
            ]
        }

        print(f"Creating OpenSearch domain: {DOMAIN_NAME}")
        response = client.create_domain(
            DomainName=DOMAIN_NAME,
            EngineVersion='OpenSearch_2.5',
            ClusterConfig=cluster_config,
            VPCOptions=vpc_options,
            EBSOptions={
                'EBSEnabled': True,
                'VolumeType': 'gp3',
                'VolumeSize': 10
            },
            AccessPolicies=json.dumps(access_policies),
            EncryptionAtRestOptions=encryption_at_rest,
            NodeToNodeEncryptionOptions={
                'Enabled': True
            },
            DomainEndpointOptions={
                'EnforceHTTPS': True,
                'TLSSecurityPolicy': 'Policy-Min-TLS-1-2-2019-07'
            },
            AdvancedSecurityOptions={
                'Enabled': True,
                'InternalUserDatabaseEnabled': True,
                'MasterUserOptions': {
                    'MasterUserName': 'admin',
                    'MasterUserPassword': 'Change-me-immediately!'  # Should be changed after setup
                }
            },
            TagList=[
                {
                    'Key': 'Project',
                    'Value': PROJECT_NAME
                }
            ]
        )

        # Wait for domain to be created
        print("Waiting for OpenSearch domain to be created (this may take 15-20 minutes)...")
        waiter = client.get_waiter('domain_available')
        waiter.wait(
            DomainName=DOMAIN_NAME,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 40}
        )

        return response['DomainStatus']

    except ClientError as e:
        print(f"Error creating OpenSearch domain: {e}")
        sys.exit(1)

def create_search_security_group(ec2, vpc_id):
    """Create security group for OpenSearch"""
    try:
        security_group = ec2.create_security_group(
            GroupName=f'{PROJECT_NAME}-search-sg',
            Description='Security group for OpenSearch domain',
            VpcId=vpc_id
        )
        
        # Add inbound rules - only allow access from application security group
        ec2.authorize_security_group_ingress(
            GroupId=security_group['GroupId'],
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'UserIdGroupPairs': [{
                        'GroupId': security_group['GroupId']  # Self-reference for testing
                    }]
                }
            ]
        )
        return security_group['GroupId']
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidGroup.Duplicate':
            response = ec2.describe_security_groups(
                Filters=[{'Name': 'group-name', 'Values': [f'{PROJECT_NAME}-search-sg']}]
            )
            return response['SecurityGroups'][0]['GroupId']
        raise e

def setup_index_mappings(domain_endpoint):
    """Set up index mappings for messages and attachments"""
    # This would typically use the OpenSearch client to set up mappings
    # For now, we'll just print the curl commands that need to be run
    message_mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "channel_id": {"type": "keyword"},
                "user_id": {"type": "keyword"},
                "created_at": {"type": "date"},
                "attachments": {
                    "type": "nested",
                    "properties": {
                        "filename": {"type": "keyword"},
                        "content_type": {"type": "keyword"},
                        "content": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        }
                    }
                }
            }
        },
        "settings": {
            "analysis": {
                "analyzer": {
                    "file_content": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase",
                            "stop",
                            "snowball"
                        ]
                    }
                }
            }
        }
    }

    print("\nTo set up index mappings, run the following commands:")
    print(f"\ncurl -X PUT -k -u 'admin:Change-me-immediately!' \\")
    print(f"  'https://{domain_endpoint}/messages' \\")
    print(f"  -H 'Content-Type: application/json' \\")
    print(f"  -d '{json.dumps(message_mapping, indent=2)}'")

def create_iam_role_for_lambda(iam):
    """Create IAM role for Lambda to access OpenSearch"""
    try:
        role_name = f"{PROJECT_NAME}-search-indexer-role"
        
        # Create role
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )

        # Attach necessary policies
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "es:ESHttpPost",
                        "es:ESHttpPut",
                        "es:ESHttpGet"
                    ],
                    "Resource": f"arn:aws:es:{AWS_REGION}:{boto3.client('sts').get_caller_identity()['Account']}:domain/{DOMAIN_NAME}/*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject"
                    ],
                    "Resource": "arn:aws:s3:::*/*"
                }
            ]
        }

        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{PROJECT_NAME}-search-indexer-policy",
            PolicyDocument=json.dumps(policy_document)
        )

        return role['Role']['Arn']

    except ClientError as e:
        print(f"Error creating IAM role: {e}")
        sys.exit(1)

def main():
    # Initialize AWS clients
    opensearch = boto3.client('opensearch', region_name=AWS_REGION)
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    iam = boto3.client('iam', region_name=AWS_REGION)

    # Get VPC ID and subnet ID from existing resources
    # You'll need to modify this to get the actual VPC and subnet IDs
    vpc_response = ec2.describe_vpcs(
        Filters=[{'Name': 'tag:Name', 'Values': [f'{PROJECT_NAME}-vpc']}]
    )
    if not vpc_response['Vpcs']:
        print("VPC not found. Please create VPC first.")
        sys.exit(1)
    vpc_id = vpc_response['Vpcs'][0]['VpcId']

    subnet_response = ec2.describe_subnets(
        Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'tag:Name', 'Values': [f'{PROJECT_NAME}-subnet']}
        ]
    )
    if not subnet_response['Subnets']:
        print("Subnet not found. Please create subnet first.")
        sys.exit(1)
    subnet_id = subnet_response['Subnets'][0]['SubnetId']

    print("Creating security group for OpenSearch...")
    security_group_id = create_search_security_group(ec2, vpc_id)

    print("Creating IAM role for Lambda indexer...")
    lambda_role_arn = create_iam_role_for_lambda(iam)

    print("Creating OpenSearch domain...")
    domain = create_opensearch_domain(opensearch, vpc_id, subnet_id, security_group_id)

    print("\nOpenSearch domain created successfully!")
    print(f"Domain ARN: {domain['ARN']}")
    print(f"Domain Endpoint: {domain['Endpoints']['vpc']}")
    print("\nNext steps:")
    print("1. Update the master user password")
    print("2. Set up index mappings using the commands above")
    print("3. Create Lambda functions for indexing messages and attachments")
    print("4. Update the application to use OpenSearch for search functionality")

if __name__ == "__main__":
    main() 