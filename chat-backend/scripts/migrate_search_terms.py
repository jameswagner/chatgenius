import boto3
import os
import sys
from boto3.dynamodb.conditions import Key

def migrate_search_terms(table_name: str, execute: bool = False):
    """Migrate search term indices to new format"""
    print(f"\n=== Migrating search terms in table {table_name} ===")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    
    # Initialize DynamoDB
    table = boto3.resource('dynamodb').Table(table_name)
    
    # Scan for all word indices
    response = table.scan(
        FilterExpression=Key('PK').begins_with('WORD#')
    )
    
    items = response['Items']
    print(f"\nFound {len(items)} word indices to migrate")
    
    # Group by message for efficient processing
    indices_by_message = {}
    for item in items:
        message_id = item['message_id']
        if message_id not in indices_by_message:
            indices_by_message[message_id] = []
        indices_by_message[message_id].append(item)
    
    print(f"\nProcessing {len(indices_by_message)} messages")
    
    # Process each message's word indices
    for message_id, word_items in indices_by_message.items():
        print(f"\nMessage {message_id}:")
        
        # Get the message to get timestamp and channel_id
        response = table.get_item(
            Key={
                'PK': f'MSG#{message_id}',
                'SK': f'MSG#{message_id}'
            }
        )
        
        if 'Item' not in response:
            print(f"  WARNING: Message {message_id} not found, skipping word indices")
            continue
            
        message = response['Item']
        timestamp = message.get('created_at')
        channel_id = message.get('channel_id')
        
        if not timestamp or not channel_id:
            print(f"  WARNING: Message {message_id} missing timestamp or channel_id, skipping")
            continue
            
        print(f"  Found message in channel {channel_id}")
        print(f"  Processing {len(word_items)} word indices")
        
        for word_item in word_items:
            word = word_item['PK'].split('#')[1]
            print(f"\n  Word: {word}")
            print("  Before:")
            print(f"    PK: {word_item['PK']}")
            print(f"    SK: {word_item['SK']}")
            if 'GSI3PK' in word_item:
                print(f"    GSI3PK: {word_item['GSI3PK']}")
            if 'GSI3SK' in word_item:
                print(f"    GSI3SK: {word_item['GSI3SK']}")
            
            # Create new word index
            new_item = {
                'PK': f'WORD#{word}',
                'SK': f'MESSAGE#{message_id}',
                'GSI3PK': f'CONTENT#{word}',
                'GSI3SK': f'TS#{timestamp}',
                'message_id': message_id,
                'channel_id': channel_id
            }
            
            print("  After:")
            print(f"    PK: {new_item['PK']}")
            print(f"    SK: {new_item['SK']}")
            print(f"    GSI3PK: {new_item['GSI3PK']}")
            print(f"    GSI3SK: {new_item['GSI3SK']}")
            
            if execute:
                # Delete old item if it exists
                table.delete_item(
                    Key={
                        'PK': word_item['PK'],
                        'SK': word_item['SK']
                    }
                )
                
                # Write new item
                table.put_item(Item=new_item)
                print("  Migrated word index")
            
    print("\nMigration complete!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python migrate_search_terms.py <table_name> [--execute]")
        sys.exit(1)
        
    table_name = sys.argv[1]
    execute = '--execute' in sys.argv
    
    migrate_search_terms(table_name, execute) 