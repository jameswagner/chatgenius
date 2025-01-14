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

def create_channels(users: List[Dict], template: Dict) -> List[Dict]:
    """Create channels based on template configuration"""
    created_channels = []
    
    if not template or 'channels' not in template:
        raise ValueError("Template must contain 'channels' configuration")
        
    channels_data = template['channels']
    print(f"\nProcessing {len(channels_data)} channels...")

    # Get workspace ID from template or generate one based on org name
    workspace_id = template.get('workspace_id')
    if not workspace_id and 'organization' in template:
        org_name = template['organization'].get('name', '').lower().replace(' ', '_')
        workspace_id = f"{org_name}_{uuid4().hex[:8]}"
    
    print(f"Using workspace ID: {workspace_id}")
    
    for channel_data in channels_data:
        try:
            # First try to get existing channel
            existing_channel = channel_service.get_channel_by_name(channel_data['name'])
            if existing_channel:
                print(f"Found existing channel: {channel_data['name']} (id: {existing_channel.id})")
                created_channels.append(existing_channel)
            else:
                # Create new channel if it doesn't exist
                channel = channel_service.create_channel(
                    name=channel_data['name'],
                    type=channel_data.get('type', 'public'),
                    created_by=users[0].id if users else None,
                    workspace_id=workspace_id
                )
                print(f"Created channel: {channel.name} (id: {channel.id}) in workspace: {workspace_id}")
                created_channels.append(channel)
            
            # Add all users to the channel (whether new or existing)
            channel = existing_channel or channel
            print(f"\nAdding/verifying {len(users)} users in channel {channel.name}:")
            for user in users:
                try:
                    channel_service.add_channel_member(channel.id, user.id)
                    print(f"  ✓ Added {user.name} (id: {user.id}) to {channel.name}")
                except Exception as e:
                    if "already exists" in str(e):
                        print(f"  ℹ {user.name} is already a member of {channel.name}")
                    else:
                        print(f"  ✗ Failed to add {user.name} to {channel.name}: {str(e)}")
                
        except Exception as e:
            print(f"Error with channel {channel_data['name']}: {e}")
            
    if not created_channels:
        raise ValueError("No channels were created or found")
            
    return created_channels

def generate_conversation(channel: Dict, user_map: Dict, template: Dict, target_date: datetime) -> List[Dict]:
    print(f"\n=== Generating conversation for {channel['name']} on {target_date.strftime('%Y-%m-%d')} ===")
    
    # Create user context string including personalities
    user_context = "\n".join([
        f"- {u['name']} ({u['role']}): {u.get('bio', '')} Personality: {u.get('personality', '')}"
        for u in template['users']
    ])

    # Create date context
    date_context = f"\nDate: {target_date.strftime('%A, %B %d, %Y')}"

    # Create the prompt
    prompt = f"""You are generating a Slack-style conversation between team members.{date_context}

Organization Context:
{template.get('organization', {}).get('description', 'No org context provided')}
Culture: {template.get('organization', {}).get('culture', 'No culture specified')}
Communication Style: {template.get('organization', {}).get('communication_style', 'Professional')}
Current Challenges: {', '.join(template.get('organization', {}).get('challenges', []))}
    
Channel: {channel['name']}
Purpose: {channel.get('purpose', 'General discussion')}
Relevant topics: {', '.join(channel.get('topics', []))}
Topics to avoid: {', '.join(channel.get('avoid_topics', []))}

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
    parser.add_argument('--num-days', type=int, default=1, help='Number of days to generate messages for (default: 1)')
    parser.add_argument('--single-channel', action='store_true', help='Only generate messages for the first channel')
    args = parser.parse_args()
    
    # Load template
    template = load_template(args.template)
    
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
    vector_service = VectorService()
    qa_service = QAService()
    
    print("\n=== Indexing Content ===")
    
    # Index all users (async)
    for user in users:
        print(f"Indexing user {user.name}...")
        await vector_service.index_user(user.id)
    
    # Index messages from each channel (async)
    for channel in channels:
        print(f"Indexing channel {channel.name}...")
        indexed_count = await vector_service.index_channel(
            channel.id,
            start_date=start_date,
            end_date=end_date
        )
        print(f"Indexed {indexed_count} messages")
    
    # Run conversation analysis (async)
    await analyze_conversations(qa_service, channels, users)
    
    print("\nDatabase population complete!")
    print(f"Created/verified {len(users)} users")
    print(f"Created/verified {len(channels)} channels")

if __name__ == '__main__':
    asyncio.run(main()) 