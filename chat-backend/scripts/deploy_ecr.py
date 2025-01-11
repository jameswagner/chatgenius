#!/usr/bin/env python3
import boto3
import subprocess
import sys
import os

# Replace with your AWS account ID
AWS_ACCOUNT_ID = "474668398195"
AWS_REGION = "us-east-1"  # Change to your desired region
REPOSITORY_NAME = "jrw-chat-app"
DOCKER_PATH = r"C:\Program Files\Docker\Docker\resources\bin\docker"

def run_command(command):
    """Run a shell command and print output"""
    print(f"\nExecuting command:\n{command}\n")
    try:
        # Use UTF-8 encoding and capture both stdout and stderr
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace'
        )
        
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            if output:
                print(output.strip())
            # Check if process has finished
            if process.poll() is not None:
                break
        
        # Get the return code
        return_code = process.wait()
        
        # If there was an error, print stderr
        if return_code != 0:
            print("\nError output:")
            print(process.stderr.read())
            return False
            
        return True
    except Exception as e:
        print(f"\nError executing command: {str(e)}")
        return False

def main():
    # Get absolute path to the backend directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, '..'))
    print(f"Backend directory: {backend_dir}")
    
    # Check if Dockerfile exists
    dockerfile_path = os.path.join(backend_dir, "Dockerfile")
    if not os.path.exists(dockerfile_path):
        print(f"Error: Dockerfile not found at {dockerfile_path}")
        sys.exit(1)
    
    # Initialize boto3 ECR client
    ecr_client = boto3.client('ecr', region_name=AWS_REGION)

    # Create ECR repository if it doesn't exist
    try:
        ecr_client.create_repository(repositoryName=REPOSITORY_NAME)
        print(f"Created ECR repository: {REPOSITORY_NAME}")
    except ecr_client.exceptions.RepositoryAlreadyExistsException:
        print(f"Repository {REPOSITORY_NAME} already exists")
    except Exception as e:
        print(f"Error creating repository: {e}")
        sys.exit(1)

    try:
        registry = f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_REGION}.amazonaws.com"
        
        # Login to ECR
        print("\nLogging into ECR...")
        login_command = f'aws ecr get-login-password --region {AWS_REGION} | "{DOCKER_PATH}" login --username AWS --password-stdin {registry}'
        if not run_command(login_command):
            sys.exit(1)
        
        # Build Docker image
        print("\nBuilding Docker image...")
        image_uri = f"{registry}/{REPOSITORY_NAME}:latest"
        build_command = f'"{DOCKER_PATH}" build -t {REPOSITORY_NAME} -f "{dockerfile_path}" "{backend_dir}"'
        if not run_command(build_command):
            sys.exit(1)
        
        # Tag Docker image
        print("\nTagging Docker image...")
        tag_command = f'"{DOCKER_PATH}" tag {REPOSITORY_NAME}:latest {image_uri}'
        if not run_command(tag_command):
            sys.exit(1)
        
        # Push Docker image to ECR
        print("\nPushing Docker image to ECR...")
        push_command = f'"{DOCKER_PATH}" push {image_uri}'
        if not run_command(push_command):
            sys.exit(1)
        
        print(f"\nSuccessfully pushed image to ECR: {image_uri}")
        
    except Exception as e:
        print(f"Error during deployment: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 