import boto3
from botocore.exceptions import ClientError

def create_chat_table(table_name="chat_app_jrw"):
    """Create DynamoDB table with required indexes if it doesn't exist"""
    dynamodb = boto3.resource('dynamodb')
    
    try:
        table = dynamodb.Table(table_name)
        table.load()
        print(f"Table {table_name} already exists")
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
                    {'AttributeName': 'GSI4SK', 'AttributeType': 'S'},
                    {'AttributeName': 'entity_type', 'AttributeType': 'S'}
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
                    },
                    {
                        'IndexName': 'entity_type',
                        'KeySchema': [
                            {'AttributeName': 'entity_type', 'KeyType': 'HASH'}
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