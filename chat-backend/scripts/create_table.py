import boto3
from botocore.exceptions import ClientError
import datetime
import time

def ensure_gsi4_exists(table_name):
    """Ensure GSI4 exists on the table, create it if missing"""
    dynamodb = boto3.client('dynamodb')
    
    try:
        # Check if GSI4 exists
        response = dynamodb.describe_table(TableName=table_name)
        existing_gsis = response['Table'].get('GlobalSecondaryIndexes', [])
        has_gsi4 = any(gsi['IndexName'] == 'GSI4' for gsi in existing_gsis)
        
        if not has_gsi4:
            print(f"Adding GSI4 to table {table_name}...")
            dynamodb.update_table(
                TableName=table_name,
                AttributeDefinitions=[
                    {'AttributeName': 'GSI4PK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI4SK', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexUpdates=[
                    {
                        'Create': {
                            'IndexName': 'GSI4',
                            'KeySchema': [
                                {'AttributeName': 'GSI4PK', 'KeyType': 'HASH'},
                                {'AttributeName': 'GSI4SK', 'KeyType': 'RANGE'}
                            ],
                            'Projection': {'ProjectionType': 'ALL'}
                        }
                    }
                ]
            )
            print("Waiting for GSI4 to become active...")
            while True:
                response = dynamodb.describe_table(TableName=table_name)
                gsi_status = next((gsi['IndexStatus'] for gsi in response['Table'].get('GlobalSecondaryIndexes', []) 
                                 if gsi['IndexName'] == 'GSI4'), None)
                if gsi_status == 'ACTIVE':
                    break
                time.sleep(5)
            print("GSI4 is now active")
        else:
            print("GSI4 already exists")
            
    except ClientError as e:
        print(f"Error checking/creating GSI4: {str(e)}")
        raise

def create_chat_table(table_name="chat_app_jrw"):
    """Create DynamoDB table with required indexes if it doesn't exist"""
    dynamodb = boto3.resource('dynamodb')
    
    try:
        table = dynamodb.Table(table_name)
        table.load()
        print(f"Table {table_name} already exists")
        # Ensure GSI4 exists on existing table
        ensure_gsi4_exists(table_name)
        return table
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Create table with required indexes
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'PK', 'KeyType': 'HASH'},
                    {'AttributeName': 'SK', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'PK', 'AttributeType': 'S'},
                    {'AttributeName': 'SK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI2SK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI3PK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI3SK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI4PK', 'AttributeType': 'S'},
                    {'AttributeName': 'GSI4SK', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'GSI1',
                        'KeySchema': [
                            {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                            {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    },
                    {
                        'IndexName': 'GSI2',
                        'KeySchema': [
                            {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                            {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    },
                    {
                        'IndexName': 'GSI3',
                        'KeySchema': [
                            {'AttributeName': 'GSI3PK', 'KeyType': 'HASH'},
                            {'AttributeName': 'GSI3SK', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    },
                    {
                        'IndexName': 'GSI4',
                        'KeySchema': [
                            {'AttributeName': 'GSI4PK', 'KeyType': 'HASH'},
                            {'AttributeName': 'GSI4SK', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            print(f"Creating table {table_name}...")
            table.wait_until_exists()
            print(f"Table {table_name} created successfully")
            return table
        else:
            raise

if __name__ == "__main__":
    create_chat_table() 