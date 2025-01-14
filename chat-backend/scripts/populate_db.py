import os
import sys
import json
import yaml
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from uuid import uuid4
from dotenv import load_dotenv
from openai import OpenAI
import argparse
import random
import asyncio
import time
from boto3.dynamodb.conditions import Key, Attr

# Add the app directory to the path so we can import our services
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client with API key from environment
client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY')
)

from app.services.user_service import UserService
from app.services.channel_service import ChannelService
from app.services.message_service import MessageService
from app.services.vector_service import VectorService
from app.services.qa_service import QAService
from app.models.user import User
from app.models.channel import Channel
from app.models.message import Message

# Initialize services
user_service = UserService()
channel_service = ChannelService()
message_service = MessageService()
vector_service = VectorService()
qa_service = QAService()

print("\n=== Database Configuration ===")
print(f"DYNAMODB_TABLE env var: {os.getenv('DYNAMODB_TABLE')}")
print(f"Using DynamoDB table: {user_service.table.name}\n")

def load_template(template_path: str) -> Dict:
    """Load configuration from a YAML template file."""
    if not os.path.exists(template_path):
        raise ValueError(f"Template file not found: {template_path}")
        
    with open(template_path, 'r') as f:
        return yaml.safe_load(f)

def create_users(template: Dict) -> List[Dict]:
    """Create users based on template configuration"""
    created_users = []
    
    if not template or 'users' not in template:
        raise ValueError("Template must contain 'users' configuration")
        
    users_data = template['users']
    
    for user_data in users_data:
        try:
            # Check if user exists
            existing_user = user_service.get_user_by_email(user_data["email"])
            if existing_user:
                print(f"Found existing user: {existing_user.name} ({existing_user.role})")
                created_users.append(existing_user)
                continue
                
            # Create new user if doesn't exist
            user = user_service.create_user(
                email=user_data["email"],
                password=user_data.get("password", "password123"),
                name=user_data["name"],
                type=user_data.get("type", "persona"),
                role=user_data.get("role"),
                bio=user_data.get("bio")
            )
            print(f"Created new user: {user.name} ({user.role})")
            created_users.append(user)
        except ValueError as e:
            print(f"Error with user {user_data['name']}: {e}")
            
    if not created_users:
        raise ValueError("No users were created or found!")
            
    return created_users

def create_channels(users: List[User], template: Dict) -> List[Channel]:
    """Create channels from template"""
    print(f"\nProcessing {len(template.get('channels', []))} channels...")
    
    # Get workspace ID from template - required field
    workspace_id = template.get('organization', {}).get('workspace_id')
    if not workspace_id:
        raise ValueError("Template must specify organization.workspace_id")
    
    print(f"Using workspace ID from template: {workspace_id}")
    
    # First check all channels in workspace via GSI4
    print("\nChecking all channels in workspace via GSI4...")
    workspace_channels = channel_service.get_workspace_channels(workspace_id)
    print(f"Found {len(workspace_channels)} channels in workspace via GSI4:")
    for ch in workspace_channels:
        print(f"  - {ch.name} (id: {ch.id}, workspace_id: {ch.workspace_id})")
    
    # Process all channels from template
    print("\nProcessing all channels from template...")
    channels = []
    for channel_config in template.get('channels', []):
        try:
            channel = None
            channel_name = channel_config['name']
            channel_type = channel_config.get('type', 'public')
            
            # First try to get existing channel
            existing = channel_service.get_channel_by_name(channel_name)
            if existing:
                print(f"\nFound existing channel: {channel_name} (id: {existing.id})")
                channel = existing
            else:
                print(f"\nAttempting to create channel: {channel_name}")
                try:
                    channel = channel_service.create_channel(
                        name=channel_name,
                        type=channel_type,
                        workspace_id=workspace_id
                    )
                    print(f"  ✓ Created channel {channel.name} (id: {channel.id})")
                except ValueError as e:
                    if "already exists" in str(e):
                        # Try to get channel again by name - it should work now that we fixed get_channel_by_name
                        channel = channel_service.get_channel_by_name(channel_name)
                        if not channel:
                            raise ValueError(f"Could not find existing channel {channel_name}")
                        print(f"  ✓ Found existing channel {channel.name} (id: {channel.id})")
                    else:
                        raise
            
            # Always update workspace ID
            print(f"  Updating workspace ID to {workspace_id}")
            channel_service.add_channel_to_workspace(channel.id, workspace_id)
            
            # Verify the update worked
            updated = channel_service.get_channel_by_id(channel.id)
            if updated.workspace_id != workspace_id:
                print(f"  ! Warning: Failed to update workspace ID for {channel.name}")
            else:
                print(f"  ✓ Successfully updated workspace ID for {channel.name}")
            
            channels.append(updated)
            
            # Add all users to the channel
            print(f"\nAdding/verifying {len(users)} users in channel {channel.name}:")
            for user in users:
                try:
                    channel_service.add_channel_member(channel.id, user.id)
                    print(f"  ✓ Added {user.name} to {channel.name}")
                except ValueError as e:
                    print(f"  ✗ Failed to add {user.name} to {channel.name}: {str(e)}")
                    
        except Exception as e:
            print(f"Error with channel {channel_config['name']}: {e}")
            
    if not channels:
        raise ValueError("No channels were created or found")
    
    # Final verification
    print("\nFinal workspace channel verification...")
    final_workspace_channels = channel_service.get_workspace_channels(workspace_id)
    print(f"Found {len(final_workspace_channels)} channels in workspace via GSI4:")
    for ch in final_workspace_channels:
        print(f"  - {ch.name} (id: {ch.id}, workspace_id: {ch.workspace_id})")
            
    return channels

def generate_conversation(channel: Channel, users: List[User], template: Dict, target_date: datetime) -> List[Dict]:
    print(f"\n=== Generating conversation for {channel.name} on {target_date.strftime('%Y-%m-%d')} ===")
    
    # Create user ID to name mapping first
    user_map = {user.id: user for user in users}
    
    # Get recent messages from this channel before target date
    recent_messages = message_service.get_messages(
        channel_id=channel.id,
        limit=20,  
        reverse=True  # Get newest first
    )
    
    # Filter messages that are before target_date
    recent_messages = [
        msg for msg in recent_messages 
        if msg.created_at <= target_date.isoformat()
    ]
    
    # Get messages from other channels in the same workspace
    workspace_context = ""
    if channel.workspace_id:
        print(f"\nGetting context from other channels in workspace {channel.workspace_id}...")
        # Get all channels in the workspace
        workspace_channels = channel_service.get_workspace_channels(channel.workspace_id)
        print(f"Found {len(workspace_channels)} channels in workspace")
        for ch in workspace_channels:
            print(f"  - {ch.name} (id: {ch.id})")
        
        other_channels = [c for c in workspace_channels if c.id != channel.id]
        print(f"\nFiltered to {len(other_channels)} other channels (excluding current channel)")
        
        if other_channels:
            workspace_messages = []
            for other_channel in other_channels:
                print(f"\nGetting messages from channel {other_channel.name}...")
                channel_messages = message_service.get_messages(
                    channel_id=other_channel.id,
                    limit=10,  # Limit per channel to avoid overwhelming context
                    reverse=True
                )
                # Filter for messages before target date
                channel_messages = [
                    msg for msg in channel_messages 
                    if msg.created_at <= target_date.isoformat()
                ]
                print(f"Found {len(channel_messages)} messages before target date")
                if channel_messages:
                    workspace_messages.extend([
                        (msg, other_channel.name) for msg in channel_messages
                    ])
            
            if workspace_messages:
                # Sort all workspace messages by timestamp
                workspace_messages.sort(
                    key=lambda x: x[0].created_at,
                    reverse=True
                )
                print(f"\nTotal workspace context messages: {len(workspace_messages)}")
                # Format workspace context
                workspace_context = "\nRecent activity in other channels:\n" + "\n".join([
                    f"[{channel_name}] {user_map[msg.user_id].name}: {msg.content}"
                    for msg, channel_name in workspace_messages[:20]  # Limit total messages
                ])
            else:
                print("No workspace messages found before target date")
    
    # Format recent messages for context
    recent_context = ""
    if recent_messages:
        # Messages are in reverse order, so reverse them back for display
        recent_messages = list(reversed(recent_messages))
        
        # Calculate days between most recent message and target date
        most_recent_date = datetime.fromisoformat(recent_messages[-1].created_at)
        days_diff = (target_date - most_recent_date).days
        time_context = f"\nNote: The most recent message above was from {days_diff} days ago."
        
        recent_context = "\nRecent conversation context:\n" + "\n".join([
            f"{user_map[msg.user_id].name}: {msg.content}"
            for msg in recent_messages
        ]) + time_context + workspace_context
    
    # Create user context string including personalities
    user_context = "\n".join([
        f"- {u['name']} ({u['role']}): {u.get('bio', '')} Personality: {u.get('personality', '')}"
        for u in template['users']
    ])

    # Create date context
    date_context = f"\nDate: {target_date.strftime('%A, %B %d, %Y')}"

    # Find the channel config in the template
    channel_config = next(
        (c for c in template.get('channels', []) if c.get('name') == channel.name),
        template.get('channels', [{}])[0]  # Fallback to first channel if not found
    )

    # Create the prompt
    prompt = f"""You are generating a Slack-style conversation between team members.{date_context}

Organization Context:
{template.get('organization', {}).get('description', 'No org context provided')}
Culture: {template.get('organization', {}).get('culture', 'No culture specified')}
Communication Style: {template.get('organization', {}).get('communication_style', 'Professional')}
Current Challenges: {', '.join(template.get('organization', {}).get('challenges', []))}
    
Channel: {channel.name}
Purpose: {channel_config.get('purpose', 'General discussion')}
Relevant topics: {', '.join(channel_config.get('topics', []))}
Topics to avoid: {', '.join(channel_config.get('avoid_topics', []))}{recent_context}

Team members and their roles:
{user_context}

Generate a realistic conversation between these team members that:
1. Strongly reflects the organization's culture and communication style
2. Shows interpersonal dynamics and underlying tensions where they exist
3. Demonstrates each person's role, expertise, AND personality traits (especially negative ones)
4. Uses appropriate tone for the org culture (can be unprofessional/toxic if that matches the culture)
5. Includes 25-30 messages with meaningful content
6. Avoids generic pleasantries and empty responses
7. Ends with substantive messages that provide good context for the next day
8. Shows realistic workplace dynamics (e.g., power struggles, passive-aggressive behavior, or excessive formality, as appropriate)
9. References the day of the week and time of year naturally in conversation where relevant
10. If previous messages don't reflect the user or organization profile/culture, ensure that these new messages do

Remember:
- Let personality conflicts and organizational dysfunction show through naturally
- Unless it is specifically a non-work channel, keep the conversation grounded in actual work while showing interpersonal dynamics

IMPORTANT: Format each message as a JSON array of objects, with each object having exactly these fields:
{{"user_name": "Name", "content": "Message content"}}

Example format:
[
  {{"user_name": "John Smith", "content": "Good morning team!"}},
  {{"user_name": "Jane Doe", "content": "Morning John, I've got the report ready."}}
]
"""

    print("\n=== OpenAI Prompt ===")
    print(prompt)
    print("\n=== End Prompt ===\n")
    
    try:
        print("Sending request to OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates realistic workplace conversations. Always format output as valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9
        )
        
        # Parse the response and return the messages
        conversation_text = response.choices[0].message.content
        
        # Clean up the response text
        cleaned_text = conversation_text.strip()
        if not cleaned_text.startswith('['):
            print("Response doesn't start with '[', attempting to find JSON array...")
            # Try to find the JSON array in the response
            start_idx = cleaned_text.find('[')
            end_idx = cleaned_text.rfind(']')
            if start_idx != -1 and end_idx != -1:
                cleaned_text = cleaned_text[start_idx:end_idx + 1]
            else:
                raise ValueError("Could not find JSON array in response")
        
        try:
            messages = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print("Attempting to fix common JSON formatting issues...")
            # Try to fix common JSON formatting issues
            cleaned_text = cleaned_text.replace("}\n{", "},{")  # Fix newlines between objects
            cleaned_text = cleaned_text.replace("},]", "}]")    # Fix trailing comma
            cleaned_text = cleaned_text.replace(",]", "]")      # Fix trailing comma
            messages = json.loads(cleaned_text)
        
        print(f"Successfully parsed {len(messages)} messages from response")
        
        # Validate message format
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise ValueError(f"Message {i} is not an object: {msg}")
            if 'user_name' not in msg or 'content' not in msg:
                raise ValueError(f"Message {i} missing required fields: {msg}")
        
        return messages
        
    except Exception as e:
        print(f"Error generating conversation: {str(e)}")
        print("Full error details:", e)
        return []

def create_messages(channel, users, messages_data, target_date: datetime):
    """Create messages in the channel based on the generated conversation"""
    # Create maps of both names->users and ids->users
    name_to_user = {user.name: user for user in users}
    user_map = {user.id: user for user in users}
    print("\nUser maps:")
    print("By name:")
    for name, user in name_to_user.items():
        print(f"  {name} -> {user.id}")
    print("\nBy ID:")
    for id, user in user_map.items():
        print(f"  {id} -> {user.name}")
    
    # Track created messages by index for threading
    message_map = {}
    
    # Set to beginning of work day (9 AM UTC)
    current_time = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    print(f"\nCreating messages for channel {channel.name}:")
    print(f"  Starting from: {current_time}")
    print(f"  Total messages to create: {len(messages_data)}")
    
    for i, msg_data in enumerate(messages_data):
        try:
            # Get the sender
            user = name_to_user.get(msg_data["user_name"])
            if not user:
                print(f"  ✗ User not found with name: {msg_data['user_name']}")
                print(f"  Available users: {list(name_to_user.keys())}")
                continue
            
            # Calculate message timestamp
            minutes = random.randint(2, 10)
            current_time += timedelta(minutes=minutes)
            timestamp = current_time.isoformat()
            
            print(f"\n  Creating message {i}:")
            print(f"    User: {user.name} ({user.id})")
            print(f"    Content: {msg_data['content'][:50]}...")
            print(f"    Timestamp: {timestamp}")
            
            # Create the message
            message = message_service.create_message(
                channel_id=channel.id,
                user_id=user.id,
                content=msg_data["content"],
                created_at=timestamp
            )
            
            # Store the message for thread reference
            message_map[i] = message
            print(f"  ✓ Created message from {user.name} at {timestamp}")
            
        except Exception as e:
            print(f"  ✗ Error creating message {i}:")
            print(f"    Error type: {type(e).__name__}")
            print(f"    Error message: {str(e)}")
            print(f"    Message data: {msg_data}")
    
    print(f"\nSummary for channel {channel.name}:")
    print(f"  Total messages created: {len(message_map)}")
    print(f"  Time span: {target_date} to {current_time}")
    
    return message_map

def delete_channel_messages(channel_id: str):
    """Delete all messages in a channel"""
    print(f"\nDeleting messages from channel {channel_id}...")
    try:
        # Get all messages in the channel using GSI1
        messages = message_service.get_messages(channel_id)
        
        if not messages:
            print("  No messages found to delete")
            return
            
        print(f"Found {len(messages)} messages to delete")
        
        # Delete each message and its word indices
        for message in messages:
            # Delete main message entry
            message_service.table.delete_item(
                Key={
                    'PK': f'MSG#{message.id}',
                    'SK': f'MSG#{message.id}'
                }
            )
            
            # Delete word index entries
            if message.content:
                words = set(message.content.lower().split())
                for word in words:
                    message_service.table.delete_item(
                        Key={
                            'PK': f'WORD#{word}',
                            'SK': f'MESSAGE#{message.id}'
                        }
                    )
                    
        print(f"  ✓ Deleted {len(messages)} messages and their word indices")
        
    except Exception as e:
        print(f"  ✗ Error deleting messages: {str(e)}")
        print(f"    Error type: {type(e).__name__}")
        raise

def delete_channel(channel: Channel):
    """Delete a channel and all its associated data (messages, memberships, etc)"""
    print(f"\nDeleting channel {channel.name} (id: {channel.id})...")
    try:
        # First delete all messages
        delete_channel_messages(channel.id)
        
        # Delete channel memberships
        print("Deleting channel memberships...")
        response = channel_service.table.query(
            KeyConditionExpression=Key('PK').eq(f'CHANNEL#{channel.id}') & 
                                 Key('SK').begins_with('MEMBER#')
        )
        for item in response['Items']:
            channel_service.table.delete_item(
                Key={
                    'PK': item['PK'],
                    'SK': item['SK']
                }
            )
        print(f"  ✓ Deleted {len(response['Items'])} channel memberships")
        
        # Delete channel metadata
        print("Deleting channel metadata...")
        channel_service.table.delete_item(
            Key={
                'PK': f'CHANNEL#{channel.id}',
                'SK': '#METADATA'
            }
        )
        print("  ✓ Deleted channel metadata")
        
    except Exception as e:
        print(f"  ✗ Error deleting channel: {str(e)}")
        raise

async def analyze_conversations(qa_service: QAService, channels: List[Channel], users: List[User]):
    """Analyze conversations using QA service to characterize topics and users."""
    print("\n=== Conversation Analysis ===")
    
    # Analyze main discussion topics for each channel
    for channel in channels:
        print(f"\nChannel: {channel.name}")
        response = await qa_service.ask_about_channel(
            channel.id,
            "What are the main topics and themes discussed in this channel? What is the overall tone of discussion?"
        )
        print(f"Topics & Tone: {response}")

    # Analyze each user's communication style and contributions
    print("\n=== User Analysis ===")
    for user in users:
        print(f"\nUser: {user.name}")
        response = await qa_service.ask_about_user(
            user.id,
            "How would you characterize this person's communication style, main topics of discussion, and typical interactions with others?",
            include_channel_context=True  # Include broader context
        )
        print(f"Profile: {response}")

async def main():
    parser = argparse.ArgumentParser(description='Populate database with template data')
    parser.add_argument('--template', required=True, help='Path to template YAML file')
    parser.add_argument('--start-date', help='Start date for messages (YYYY-MM-DD)')
    parser.add_argument('--delete-messages', action='store_true', help='Delete existing messages before creating new ones')
    parser.add_argument('--delete-channels', action='store_true', help='Delete all channels specified in template before creating new ones')
    parser.add_argument('--num-days', type=int, default=1, help='Number of days to generate messages for (default: 1)')
    parser.add_argument('--single-channel', action='store_true', help='Only generate messages for the first channel')
    args = parser.parse_args()
    
    # Load template
    template = load_template(args.template)
    
    if args.delete_channels:
        print("\n=== Deleting existing channels ===")
        workspace_id = template.get('organization', {}).get('workspace_id')
        if not workspace_id:
            raise ValueError("Template must specify organization.workspace_id")
            
        # Get all channels in workspace
        workspace_channels = channel_service.get_workspace_channels(workspace_id)
        template_channel_names = {ch['name'] for ch in template.get('channels', [])}
        
        # Delete channels that match template names
        for channel in workspace_channels:
            if channel.name in template_channel_names:
                delete_channel(channel)
        
        print("\nChannel deletion complete!")
        return  # Exit after channel deletion
    
    # Create users and channels
    users = create_users(template)
    channels = create_channels(users, template)
    
    if args.single_channel:
        channels = channels[:1]
        print(f"\nSingle channel mode - only generating messages for: {channels[0].name}")
    
    # Calculate dates to generate messages for
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        # Backdate from today
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=args.num_days-1)
    
    end_date = start_date + timedelta(days=args.num_days-1)
    print(f"\nGenerating messages from {start_date.date()} to {end_date.date()}")
    
    if args.delete_messages:
        print("Deleting existing messages...")
        for channel in channels:
            delete_channel_messages(channel.id)
    
    # Create messages for each day and channel
    current_date = start_date
    while current_date <= end_date:
        print(f"\n=== Generating messages for {current_date.date()} ===")
        
        for channel in channels:
            print(f"\nGenerating conversation for channel {channel.name}...")
            messages = generate_conversation(
                channel,
                users,
                template,
                target_date=current_date
            )
            if messages:
                create_messages(channel, users, messages, current_date)
        
        current_date += timedelta(days=1)
    
    # Initialize services for async operations
    # vector_service = VectorService()
    # qa_service = QAService()
    
    # print("\n=== Indexing Content ===")
    
    # # Index all users (async)
    # for user in users:
    #     print(f"Indexing user {user.name}...")
    #     await vector_service.index_user(user.id)
    
    # # Index messages from each channel (async)
    # for channel in channels:
    #     print(f"Indexing channel {channel.name}...")
    #     indexed_count = await vector_service.index_channel(
    #         channel.id,
    #         start_date=start_date,
    #         end_date=end_date
    #     )
    #     print(f"Indexed {indexed_count} messages")
    
    # # Run conversation analysis (async)
    # await analyze_conversations(qa_service, channels, users)
    
    print("\nDatabase population complete!")
    print(f"Created/verified {len(users)} users")
    print(f"Created/verified {len(channels)} channels")

if __name__ == '__main__':
    asyncio.run(main()) 