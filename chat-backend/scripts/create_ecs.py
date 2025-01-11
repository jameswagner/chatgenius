#!/usr/bin/env python3
import boto3
import time
import sys
from botocore.exceptions import ClientError

# Configuration
PROJECT_NAME = "jrw-chat-app"
AWS_REGION = "us-east-1"
VPC_CIDR = "10.0.0.0/16"
CONTAINER_PORT = 5000
DOMAIN_NAME = "chat.jrw.com"  # Replace with your domain

def create_vpc(ec2):
    """Create VPC with public and private subnets"""
    try:
        # Create VPC
        vpc = ec2.create_vpc(
            CidrBlock=VPC_CIDR,
            TagSpecifications=[{
                'ResourceType': 'vpc',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-vpc'}]
            }]
        )
        vpc.wait_until_available()
        
        # Enable DNS hostnames in the VPC
        ec2.modify_vpc_attribute(VpcId=vpc.id, EnableDnsHostnames={'Value': True})
        ec2.modify_vpc_attribute(VpcId=vpc.id, EnableDnsSupport={'Value': True})
        
        # Create Internet Gateway
        igw = ec2.create_internet_gateway(
            TagSpecifications=[{
                'ResourceType': 'internet-gateway',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-igw'}]
            }]
        )
        vpc.attach_internet_gateway(InternetGatewayId=igw.id)
        
        # Create public subnets in different AZs
        public_subnets = []
        private_subnets = []
        azs = ec2.describe_availability_zones()['AvailabilityZones']
        
        for i, az in enumerate(azs[:2]):  # Create in first 2 AZs
            # Public subnet
            public_subnet = ec2.create_subnet(
                VpcId=vpc.id,
                CidrBlock=f"10.0.{i*2}.0/24",
                AvailabilityZone=az['ZoneName'],
                TagSpecifications=[{
                    'ResourceType': 'subnet',
                    'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-public-{az["ZoneName"]}'}]
                }]
            )
            public_subnets.append(public_subnet)
            
            # Private subnet
            private_subnet = ec2.create_subnet(
                VpcId=vpc.id,
                CidrBlock=f"10.0.{i*2+1}.0/24",
                AvailabilityZone=az['ZoneName'],
                TagSpecifications=[{
                    'ResourceType': 'subnet',
                    'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-private-{az["ZoneName"]}'}]
                }]
            )
            private_subnets.append(private_subnet)
        
        # Create and configure route tables
        public_rt = ec2.create_route_table(
            VpcId=vpc.id,
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-public-rt'}]
            }]
        )
        public_rt.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=igw.id)
        
        for subnet in public_subnets:
            public_rt.associate_with_subnet(SubnetId=subnet.id)
        
        # Create NAT Gateway for private subnets
        eip = ec2.allocate_address(Domain='vpc')
        nat_gateway = ec2.create_nat_gateway(
            SubnetId=public_subnets[0].id,
            AllocationId=eip.allocation_id,
            TagSpecifications=[{
                'ResourceType': 'natgateway',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-nat'}]
            }]
        )
        
        # Wait for NAT Gateway to be available
        waiter = ec2.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[nat_gateway.id])
        
        # Create private route table with NAT Gateway
        private_rt = ec2.create_route_table(
            VpcId=vpc.id,
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-private-rt'}]
            }]
        )
        private_rt.create_route(DestinationCidrBlock='0.0.0.0/0', NatGatewayId=nat_gateway.id)
        
        for subnet in private_subnets:
            private_rt.associate_with_subnet(SubnetId=subnet.id)
        
        return {
            'vpc': vpc,
            'public_subnets': public_subnets,
            'private_subnets': private_subnets
        }
        
    except ClientError as e:
        print(f"Error creating VPC: {e}")
        sys.exit(1)

def create_security_groups(ec2, vpc_id):
    """Create security groups for ALB and ECS tasks"""
    try:
        # ALB Security Group
        alb_sg = ec2.create_security_group(
            GroupName=f'{PROJECT_NAME}-alb-sg',
            Description='Security group for ALB',
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-alb-sg'}]
            }]
        )
        
        alb_sg.authorize_ingress(
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        
        # ECS Security Group
        ecs_sg = ec2.create_security_group(
            GroupName=f'{PROJECT_NAME}-ecs-sg',
            Description='Security group for ECS tasks',
            VpcId=vpc_id,
            TagSpecifications=[{
                'ResourceType': 'security-group',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-ecs-sg'}]
            }]
        )
        
        ecs_sg.authorize_ingress(
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': CONTAINER_PORT,
                'ToPort': CONTAINER_PORT,
                'UserIdGroupPairs': [{'GroupId': alb_sg.id}]
            }]
        )
        
        return {
            'alb_sg': alb_sg,
            'ecs_sg': ecs_sg
        }
        
    except ClientError as e:
        print(f"Error creating security groups: {e}")
        sys.exit(1)

def create_certificate(acm):
    """Create ACM certificate"""
    try:
        # Request certificate
        certificate = acm.request_certificate(
            DomainName=DOMAIN_NAME,
            ValidationMethod='DNS',
            Tags=[{'Key': 'Name', 'Value': f'{PROJECT_NAME}-cert'}]
        )
        
        print(f"\nCertificate requested. Please add the following DNS records to validate the certificate:")
        
        # Wait for certificate details to be available
        waiter = acm.get_waiter('certificate_validated')
        print("Waiting for certificate validation... This may take several minutes.")
        print("You must add the DNS validation records to your domain for this to complete.")
        
        try:
            waiter.wait(
                CertificateArn=certificate['CertificateArn'],
                WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
            )
        except Exception as e:
            print(f"Certificate validation timed out: {e}")
            print("Please check the AWS Console and ensure DNS validation is complete.")
        
        return certificate['CertificateArn']
        
    except ClientError as e:
        print(f"Error creating certificate: {e}")
        sys.exit(1)

def create_load_balancer(elbv2, public_subnet_ids, security_group_id, certificate_arn):
    """Create Application Load Balancer with HTTPS"""
    try:
        # Create ALB
        alb = elbv2.create_load_balancer(
            Name=f'{PROJECT_NAME}-alb',
            Subnets=public_subnet_ids,
            SecurityGroups=[security_group_id],
            Scheme='internet-facing',
            Tags=[{'Key': 'Name', 'Value': f'{PROJECT_NAME}-alb'}]
        )['LoadBalancers'][0]
        
        # Wait for ALB to be active
        waiter = elbv2.get_waiter('load_balancer_available')
        waiter.wait(LoadBalancerArns=[alb['LoadBalancerArn']])
        
        # Create target group
        target_group = elbv2.create_target_group(
            Name=f'{PROJECT_NAME}-tg',
            Protocol='HTTP',
            Port=CONTAINER_PORT,
            VpcId=vpc_id,
            HealthCheckPath='/health',
            HealthCheckIntervalSeconds=30,
            HealthCheckTimeoutSeconds=5,
            HealthyThresholdCount=2,
            UnhealthyThresholdCount=2,
            TargetType='ip'
        )['TargetGroups'][0]
        
        # Create HTTPS listener with certificate
        https_listener = elbv2.create_listener(
            LoadBalancerArn=alb['LoadBalancerArn'],
            Protocol='HTTPS',
            Port=443,
            Certificates=[{'CertificateArn': certificate_arn}],
            DefaultActions=[{
                'Type': 'forward',
                'TargetGroupArn': target_group['TargetGroupArn']
            }]
        )
        
        # Create HTTP listener that redirects to HTTPS
        http_listener = elbv2.create_listener(
            LoadBalancerArn=alb['LoadBalancerArn'],
            Protocol='HTTP',
            Port=80,
            DefaultActions=[{
                'Type': 'redirect',
                'RedirectConfig': {
                    'Protocol': 'HTTPS',
                    'Port': '443',
                    'StatusCode': 'HTTP_301'
                }
            }]
        )
        
        return {
            'alb': alb,
            'target_group': target_group,
            'https_listener': https_listener,
            'http_listener': http_listener
        }
        
    except ClientError as e:
        print(f"Error creating load balancer: {e}")
        sys.exit(1)

def create_ecs_cluster(ecs):
    """Create ECS cluster"""
    try:
        cluster = ecs.create_cluster(
            clusterName=f'{PROJECT_NAME}-cluster',
            capacityProviders=['FARGATE'],
            defaultCapacityProviderStrategy=[{
                'capacityProvider': 'FARGATE',
                'weight': 1
            }],
            tags=[{'key': 'Name', 'value': f'{PROJECT_NAME}-cluster'}]
        )
        return cluster
        
    except ClientError as e:
        print(f"Error creating ECS cluster: {e}")
        sys.exit(1)

def main():
    # Initialize AWS clients
    ec2 = boto3.resource('ec2', region_name=AWS_REGION)
    ecs = boto3.client('ecs', region_name=AWS_REGION)
    elbv2 = boto3.client('elbv2', region_name=AWS_REGION)
    acm = boto3.client('acm', region_name=AWS_REGION)
    
    print("Creating VPC and networking components...")
    vpc_resources = create_vpc(ec2)
    
    print("Creating security groups...")
    security_groups = create_security_groups(ec2, vpc_resources['vpc'].id)
    
    print("Requesting SSL certificate...")
    certificate_arn = create_certificate(acm)
    
    print("Creating Application Load Balancer...")
    public_subnet_ids = [subnet.id for subnet in vpc_resources['public_subnets']]
    alb_resources = create_load_balancer(elbv2, public_subnet_ids, security_groups['alb_sg'].id, certificate_arn)
    
    print("Creating ECS cluster...")
    cluster = create_ecs_cluster(ecs)
    
    print("\nInfrastructure creation completed!")
    print(f"VPC ID: {vpc_resources['vpc'].id}")
    print(f"ALB DNS Name: {alb_resources['alb']['DNSName']}")
    print(f"ECS Cluster: {cluster['cluster']['clusterName']}")
    print(f"Certificate ARN: {certificate_arn}")
    print("\nIMPORTANT: Make sure to:")
    print("1. Add the DNS validation records to your domain to validate the certificate")
    print(f"2. Create a CNAME record pointing {DOMAIN_NAME} to {alb_resources['alb']['DNSName']}")

if __name__ == "__main__":
    main() 