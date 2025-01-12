import os
import sys
import boto3
from boto3.dynamodb.conditions import Key, Attr
from typing import List, Dict
from datetime import datetime

def migrate_messages(table_name: str, dry_run: bool = True) -> None:
    """
    Migrate messages from old format (CHANNEL#<channel_id>/MSG#<timestamp>#<message_id>)
    to new format (MSG#<message_id>/MSG#<message_id>) with:
    - GSI1 for channel lookup (CHANNEL#{channel_id}/TS#{timestamp})
    - GSI2 for user lookup (USER#{user_id}/TS#{timestamp})
    """
    print(f"\n=== Starting message migration ===")
    print(f"Table: {table_name}")
    print(f"Dry run: {dry_run}")
    
    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Scan for all messages in old format (only actual messages, not word indices)
    response = table.scan(
        FilterExpression=Attr('SK').begins_with('MSG#') & Attr('PK').begins_with('CHANNEL#')
    )
    
    items = response['Items']
    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression=Attr('SK').begins_with('MSG#') & Attr('PK').begins_with('CHANNEL#'),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        items.extend(response['Items'])
    
    print(f"\nFound {len(items)} messages to migrate")
    
    messages_without_gsi1sk: List[Dict] = []
    sample_count = 0
    total_migrated = 0
    
    for message in items:
        try:
            channel_id = message['PK'].split('#')[1]
            user_id = message.get('user_id')
            
            # Track messages without GSI1SK
            if 'GSI1SK' not in message:
                messages_without_gsi1sk.append(message)
            
            # Extract message ID and timestamp from SK
            parts = message['SK'].split('#')
            timestamp = parts[1]
            message_id = parts[2]
            
            # Create new format item
            new_item = message.copy()
            new_item['PK'] = f'MSG#{message_id}'
            new_item['SK'] = f'MSG#{message_id}'
            
            # GSI1 for channel lookup
            new_item['GSI1PK'] = f'CHANNEL#{channel_id}'
            new_item['GSI1SK'] = f'TS#{timestamp}'
            
            # GSI2 for user lookup
            if user_id:
                new_item['GSI2PK'] = f'USER#{user_id}'
                new_item['GSI2SK'] = f'TS#{timestamp}'
            
            # Show sample of transformations
            if sample_count < 5:
                print("\nSample message transformation:")
                print("Before:")
                for key, value in sorted(message.items()):
                    print(f"  {key}: {value}")
                print("\nAfter:")
                for key, value in sorted(new_item.items()):
                    print(f"  {key}: {value}")
                print("\n" + "-"*50)
                sample_count += 1
            
            if not dry_run:
                # Write new format
                table.put_item(Item=new_item)
            
            total_migrated += 1
        except Exception as e:
            print(f"Error processing message: {e}")
            print(f"Message data: {message}")
            continue
    
    print(f"\n=== Migration complete ===")
    print(f"Total messages {'would be ' if dry_run else ''}migrated: {total_migrated}")
    
    if messages_without_gsi1sk:
        print("\n=== Messages without GSI1SK ===")
        print(f"Found {len(messages_without_gsi1sk)} messages")
        print("\nSample of messages without GSI1SK:")
        for i, msg in enumerate(messages_without_gsi1sk[:5]):
            print(f"\nMessage {i+1}:")
            for key, value in sorted(msg.items()):
                print(f"  {key}: {value}")
            if 'created_at' in msg:
                try:
                    created_at = datetime.fromisoformat(msg['created_at'].replace('Z', '+00:00'))
                    print(f"  Created: {created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                except:
                    pass
    
    if dry_run:
        print("\nThis was a dry run. Run with --execute to perform the actual migration.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python migrate_messages.py <table_name> [--execute]")
        sys.exit(1)
        
    table_name = sys.argv[1]
    dry_run = '--execute' not in sys.argv
    
    migrate_messages(table_name, dry_run) 