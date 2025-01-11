#!/usr/bin/env python3
import boto3
import base64
import sys
from botocore.exceptions import ClientError

# Configuration
PROJECT_NAME = "jrw-chat-app"
AWS_REGION = "us-east-1"
INSTANCE_TYPE = "t2.micro"
UBUNTU_AMI = "ami-0c7217cdde317cfec"  # Ubuntu 22.04 LTS in us-east-1
VPC_CIDR = "10.0.0.0/16"

def create_vpc(ec2):
    """Create VPC with public subnet or use existing one"""
    try:
        # Check for existing VPC
        existing_vpcs = ec2.describe_vpcs(
            Filters=[
                {'Name': 'tag:Name', 'Values': [f'{PROJECT_NAME}-vpc']}
            ]
        )
        
        if existing_vpcs['Vpcs']:
            print(f"Found existing VPC with name {PROJECT_NAME}-vpc")
            vpc_id = existing_vpcs['Vpcs'][0]['VpcId']
            
            # Get existing subnet
            existing_subnets = ec2.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'tag:Name', 'Values': [f'{PROJECT_NAME}-subnet']}
                ]
            )
            
            if existing_subnets['Subnets']:
                print(f"Found existing subnet in VPC")
                return {
                    'vpc_id': vpc_id,
                    'subnet_id': existing_subnets['Subnets'][0]['SubnetId']
                }
            
            print("Creating new subnet in existing VPC...")
            # Create new subnet in existing VPC
            subnet = ec2.create_subnet(
                VpcId=vpc_id,
                CidrBlock="10.0.1.0/24",
                AvailabilityZone=f"{AWS_REGION}a",
                TagSpecifications=[{
                    'ResourceType': 'subnet',
                    'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-subnet'}]
                }]
            )
            
            # Enable auto-assign public IP
            ec2.modify_subnet_attribute(
                SubnetId=subnet['Subnet']['SubnetId'],
                MapPublicIpOnLaunch={'Value': True}
            )
            
            return {
                'vpc_id': vpc_id,
                'subnet_id': subnet['Subnet']['SubnetId']
            }

        print("No existing VPC found, creating new one...")
        # Create VPC
        vpc = ec2.create_vpc(
            CidrBlock=VPC_CIDR,
            TagSpecifications=[{
                'ResourceType': 'vpc',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-vpc'}]
            }]
        )

        # Enable DNS hostnames and support
        ec2.modify_vpc_attribute(VpcId=vpc['Vpc']['VpcId'], EnableDnsHostnames={'Value': True})
        ec2.modify_vpc_attribute(VpcId=vpc['Vpc']['VpcId'], EnableDnsSupport={'Value': True})

        # Create Internet Gateway
        igw = ec2.create_internet_gateway(
            TagSpecifications=[{
                'ResourceType': 'internet-gateway',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-igw'}]
            }]
        )
        ec2.attach_internet_gateway(
            InternetGatewayId=igw['InternetGateway']['InternetGatewayId'],
            VpcId=vpc['Vpc']['VpcId']
        )

        # Create public subnet
        subnet = ec2.create_subnet(
            VpcId=vpc['Vpc']['VpcId'],
            CidrBlock="10.0.1.0/24",
            AvailabilityZone=f"{AWS_REGION}a",
            TagSpecifications=[{
                'ResourceType': 'subnet',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-subnet'}]
            }]
        )

        # Create and configure route table
        route_table = ec2.create_route_table(
            VpcId=vpc['Vpc']['VpcId'],
            TagSpecifications=[{
                'ResourceType': 'route-table',
                'Tags': [{'Key': 'Name', 'Value': f'{PROJECT_NAME}-rt'}]
            }]
        )

        # Add route to Internet Gateway
        ec2.create_route(
            RouteTableId=route_table['RouteTable']['RouteTableId'],
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw['InternetGateway']['InternetGatewayId']
        )

        # Associate route table with subnet
        ec2.associate_route_table(
            RouteTableId=route_table['RouteTable']['RouteTableId'],
            SubnetId=subnet['Subnet']['SubnetId']
        )

        # Enable auto-assign public IP
        ec2.modify_subnet_attribute(
            SubnetId=subnet['Subnet']['SubnetId'],
            MapPublicIpOnLaunch={'Value': True}
        )

        return {
            'vpc_id': vpc['Vpc']['VpcId'],
            'subnet_id': subnet['Subnet']['SubnetId']
        }

    except ClientError as e:
        print(f"Error with VPC operations: {e}")
        sys.exit(1)

def create_security_group(ec2, vpc_id):
    """Create security group for the EC2 instance"""
    try:
        security_group = ec2.create_security_group(
            GroupName=f'{PROJECT_NAME}-sg',
            Description='Security group for Chat Application',
            VpcId=vpc_id
        )
        
        # Add inbound rules
        ec2.authorize_security_group_ingress(
            GroupId=security_group['GroupId'],
            IpPermissions=[
                # Allow HTTP
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                # Allow HTTPS
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                # Allow SSH
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22,
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                # Allow WebSocket
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5000,
                    'ToPort': 5000,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        return security_group['GroupId']
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidGroup.Duplicate':
            response = ec2.describe_security_groups(
                Filters=[{'Name': 'group-name', 'Values': [f'{PROJECT_NAME}-sg']}]
            )
            return response['SecurityGroups'][0]['GroupId']
        raise e

def get_user_data():
    """Generate user data script for EC2 instance"""
    user_data_script = '''#!/bin/bash
# Update system
apt-get update
apt-get upgrade -y

# Install required packages
apt-get install -y python3-pip nginx supervisor git python3-venv

# Create app directory
mkdir -p /var/www/chat-app
cd /var/www/chat-app

# Clone the repository (replace with your actual repo)
git clone https://github.com/jameswagner/ChatGenius.git .
cd chat-backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt
pip install gunicorn eventlet

# Configure Supervisor
cat > /etc/supervisor/conf.d/chat-app.conf << 'EOF'
[program:chat-app]
directory=/var/www/chat-app/chat-backend
command=/var/www/chat-app/chat-backend/venv/bin/gunicorn --worker-class eventlet -w 1 app:app -b 127.0.0.1:5000
autostart=true
autorestart=true
stderr_logfile=/var/log/chat-app.err.log
stdout_logfile=/var/log/chat-app.out.log
environment=PYTHONPATH="/var/www/chat-app/chat-backend"
EOF

# Configure Nginx
cat > /etc/nginx/sites-available/chat-app << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, PUT, DELETE' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        
        # Handle preflight requests
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, PUT, DELETE';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }
}
EOF

# Enable the Nginx configuration
ln -s /etc/nginx/sites-available/chat-app /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Create required directories
mkdir -p /var/www/chat-app/chat-backend/uploads
chown -R www-data:www-data /var/www/chat-app

# Start services
systemctl restart supervisor
systemctl restart nginx

# Set up log rotation
cat > /etc/logrotate.d/chat-app << 'EOF'
/var/log/chat-app.*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 640 root root
}
EOF
'''
    return base64.b64encode(user_data_script.encode()).decode()

def create_instance_profile_for_role(iam):
    """Create instance profile for UnifiedServicesRole if it doesn't exist"""
    try:
        profile_name = "UnifiedServicesRole-profile"
        try:
            # Try to create the profile directly
            print(f"Creating instance profile: {profile_name}")
            iam.create_instance_profile(InstanceProfileName=profile_name)
            iam.add_role_to_instance_profile(
                InstanceProfileName=profile_name,
                RoleName='UnifiedServicesRole'
            )
        except iam.exceptions.EntityAlreadyExistsException:
            print(f"Instance profile already exists: {profile_name}")
        
        return profile_name
    except Exception as e:
        print(f"Error setting up instance profile: {e}")
        sys.exit(1)

def launch_ec2_instance(ec2, iam, security_group_id, subnet_id):
    """Launch EC2 instance with the application"""
    try:
        # Create or get instance profile
        profile_name = create_instance_profile_for_role(iam)
        
        instance_params = {
            'ImageId': UBUNTU_AMI,
            'InstanceType': INSTANCE_TYPE,
            'MaxCount': 1,
            'MinCount': 1,
            'SecurityGroupIds': [security_group_id],
            'SubnetId': subnet_id,
            'UserData': get_user_data(),
            'IamInstanceProfile': {'Name': profile_name},
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': PROJECT_NAME}]
            }]
        }
        
        response = ec2.run_instances(**instance_params)
        instance_id = response['Instances'][0]['InstanceId']
        
        # Wait for instance to be running
        print("Waiting for instance to be running...")
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])
        
        # Get instance public IP
        instance = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = instance['Reservations'][0]['Instances'][0]['PublicIpAddress']
        
        return instance_id, public_ip
        
    except ClientError as e:
        print(f"Error launching instance: {e}")
        sys.exit(1)

def main():
    # Initialize AWS clients
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    iam = boto3.client('iam', region_name=AWS_REGION)
    
    print("Creating VPC and subnet...")
    vpc_resources = create_vpc(ec2)
    
    print("Creating security group...")
    security_group_id = create_security_group(ec2, vpc_resources['vpc_id'])
    
    print("Launching EC2 instance...")
    instance_id, public_ip = launch_ec2_instance(ec2, iam, security_group_id, vpc_resources['subnet_id'])
    
    print(f"\nDeployment completed!")
    print(f"Instance ID: {instance_id}")
    print(f"Public IP: {public_ip}")
    print(f"\nAccess your application at: http://{public_ip}")
    print("\nImportant Notes:")
    print("1. Instance initialization may take a few minutes")
    print("2. Check deployment logs:")
    print(f"   ssh ubuntu@{public_ip}")
    print("   sudo tail -f /var/log/chat-app.err.log")
    print(f"3. Update your frontend API configuration to point to: http://{public_ip}")
    print("\nMonitoring Commands:")
    print("- Check supervisor status: sudo supervisorctl status")
    print("- Check nginx status: sudo systemctl status nginx")
    print("- View nginx logs: sudo tail -f /var/log/nginx/error.log")

if __name__ == "__main__":
    main() 