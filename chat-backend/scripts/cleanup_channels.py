import os
import boto3
from boto3.dynamodb.conditions import Key
import sys
import logging

# Add the parent directory to the Python path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.ddb import DynamoDB

def cleanup_channels():
    """Delete all channels (except general and DMs) and their messages/memberships."""
    
    db = DynamoDB()
    table = db.table
    
    # First, get all channels using GSI1 for public and private channels
    channels_to_delete = []
    for channel_type in ['public', 'private']:  # Removed 'dm' to preserve DMs
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'TYPE#{channel_type}')
        )
        
        for item in response.get('Items', []):
            if item['SK'] == '#METADATA':
                channel_id = item['id']
                if channel_id != 'general':  # Skip general channel
                    channels_to_delete.append(channel_id)

    print(f"Found {len(channels_to_delete)} channels to delete")
    
    # Delete channel memberships, messages, and channels
    for channel_id in channels_to_delete:
        print(f"Deleting channel {channel_id}...")
        
        # First delete all memberships
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel_id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        
        for member in response.get('Items', []):
            table.delete_item(
                Key={
                    'PK': member['PK'],
                    'SK': member['SK']
                }
            )
            print(f"  Deleted membership {member['SK']}")
        
        # Delete all messages in the channel
        print(f"  Deleting messages...")
        response = table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq(f'CHANNEL#{channel_id}')
        )
        
        for message in response.get('Items', []):
            # Delete main message
            table.delete_item(
                Key={
                    'PK': message['PK'],
                    'SK': message['SK']
                }
            )
            
            # If it's a parent message, delete all replies
            if message['SK'].startswith('MSG#'):
                thread_id = message['id']
                replies_response = table.query(
                    KeyConditionExpression=Key('PK').eq(f'MSG#{thread_id}') & 
                                         Key('SK').begins_with('REPLY#')
                )
                for reply in replies_response.get('Items', []):
                    table.delete_item(
                        Key={
                            'PK': reply['PK'],
                            'SK': reply['SK']
                        }
                    )
        print(f"  Deleted all messages")
        
        # Finally delete the channel metadata
        table.delete_item(
            Key={
                'PK': f'CHANNEL#{channel_id}',
                'SK': '#METADATA'
            }
        )
        print(f"  Deleted channel metadata")
    
    # Delete all search index entries
    print("\nDeleting all search index entries...")
    last_evaluated_key = None
    total_search_entries = 0
    
    while True:
        if last_evaluated_key:
            response = table.scan(
                FilterExpression=Key('PK').begins_with('WORD#'),
                ExclusiveStartKey=last_evaluated_key
            )
        else:
            response = table.scan(
                FilterExpression=Key('PK').begins_with('WORD#')
            )
        
        for item in response.get('Items', []):
            table.delete_item(
                Key={
                    'PK': item['PK'],
                    'SK': item['SK']
                }
            )
            total_search_entries += 1
            
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break
    
    print(f"Deleted {total_search_entries} search index entries")
    
    # Update general channel to have NO_WORKSPACE
    print("\nUpdating general channel...")
    table.update_item(
        Key={
            'PK': 'CHANNEL#general',
            'SK': '#METADATA'
        },
        UpdateExpression='SET workspace_id = :wid, GSI4PK = :wpk, GSI4SK = :csk',
        ExpressionAttributeValues={
            ':wid': 'NO_WORKSPACE',
            ':wpk': 'WORKSPACE#NO_WORKSPACE',
            ':csk': 'CHANNEL#general'
        }
    )
    print("General channel updated with NO_WORKSPACE")

if __name__ == '__main__':
    cleanup_channels() 