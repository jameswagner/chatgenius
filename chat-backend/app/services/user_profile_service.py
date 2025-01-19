from typing import Optional, List
from boto3.dynamodb.conditions import Key
from app.models.user_profile import UserProfile
from .base_service import BaseService
import boto3
import os
from datetime import datetime, timezone, timedelta
from langchain.chat_models import ChatOpenAI
from app.services.vector_service import VectorService
from app.services.user_service import UserService
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

class UserProfileService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )

        # Initialize embedding model
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Initialize Pinecone vector store
        self.index_name = os.getenv("PINECONE_INDEX")
        
        self.pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=self.index_name
        )
        self.table_name = table_name

    def store_user_profile(self, user_id: str, profile_data: dict) -> UserProfile:
        """Store a new user profile for a given user with a timestamp-based sort key."""
        if 'profile_id' not in profile_data:
            profile_data['profile_id'] = f'PROFILE#{datetime.now(timezone.utc).isoformat()}'
        profile_id = profile_data['profile_id']
        profile_data = {
            'PK': f'USER#{user_id}',
            'SK': profile_id,
            'user_id': user_id,
            'entity_type': 'USER_PROFILE',
            **profile_data
        }
        self.table.put_item(Item=profile_data)
        # remove the PK and SK from the profile data
        profile_data.pop('PK', None)
        profile_data.pop('SK', None)
        return UserProfile(**profile_data)

    def get_user_profiles(self, user_id: str) -> List[UserProfile]:
        """Retrieve all profiles for a given user."""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('PROFILE#')
        )
        for item in response.get('Items', []):
            item.pop('PK', None)
            item.pop('SK', None)
        return [UserProfile(**item) for item in response.get('Items', [])]

    def get_most_recent_profile(self, user_id: str) -> Optional[UserProfile]:
        """Retrieve the most recent profile for a given user."""
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('PROFILE#'),
            ScanIndexForward=False,
            Limit=1
        )
        items = response.get('Items', [])
        for item in items:
            item.pop('PK', None)
            item.pop('SK', None)
        return UserProfile(**items[0]) if items else None 

    async def update_user_profiles(self, user_id: str):
        """Update user profiles by retrieving messages and generating new profiles using LLM."""
        # Retrieve the most recent profile
        most_recent_profile = self.get_most_recent_profile(user_id)
        last_message_timestamp = most_recent_profile.last_message_timestamp_epoch if most_recent_profile else int(datetime(2024, 10, 1, tzinfo=timezone.utc).timestamp())

        # Initialize LLM
        llm = ChatOpenAI(temperature=0.4, model="gpt-4")

        # Set initial timestamps
        current_timestamp = datetime.now(timezone.utc)
        start_timestamp_epoch = int(float(last_message_timestamp))

        # Retrieve the User object
        user_service = UserService(self.table_name)
        user = user_service.get_user_by_id(user_id)

        user_name = user.name if user else "Unknown"
        user_role = user.role if user else "Unknown"
        user_bio = user.bio if user else "No bio available"
        
        vector_store = self.index
        
        # Set initial timestamps in epoch        
        oct_22_epoch = int(datetime(2024, 10, 15, tzinfo=timezone.utc).timestamp())
        print(f"start_timestamp_epoch: {start_timestamp_epoch}")

        while start_timestamp_epoch < oct_22_epoch:
            print(f"start_timestamp_epoch: {start_timestamp_epoch}")
            end_timestamp_epoch = start_timestamp_epoch + 86400  # Increment by 1 day in seconds
            message_groups = []

            # Increment end_timestamp_epoch until at least 50 message groups are retrieved
            while len(message_groups) < 10 and end_timestamp_epoch < oct_22_epoch:
                print(f"start_timestamp_epoch: {start_timestamp_epoch}")
                print(f"end_timestamp_epoch: {end_timestamp_epoch}")
                # Create retriever with enhanced parameters
                filtered_retriever = vector_store.as_retriever(
                    search_type="mmr",
                    search_kwargs={
                        "k": 1000,  # Number of results to return
                        "fetch_k": 10000,  # Number of initial results to fetch before MMR
                        "lambda_mult": 0.7,  # Increased from 0.5 to favor relevance over diversity
                        "namespace": "grouped_messages",
                        "filter": {
                            "user_ids": {"$eq": user_id},
                            "end_timestamp_epoch": {"$gte": start_timestamp_epoch, "$lt": end_timestamp_epoch}
                        },
                        "score_threshold": 0.7  # Only return results with cosine similarity above this
                    }
                )

                # Use a generic search query
                search_query = "Retrieve messages for user profile update"

                # Retrieve message groups
                message_groups = await filtered_retriever.ainvoke(search_query)

                # Increment end_timestamp_epoch by 1 day and update start_timestamp_epoch for sliding window
                start_timestamp_epoch = end_timestamp_epoch
                end_timestamp_epoch += 86400

            print(f"Retrieved {len(message_groups)} message groups")  
            if len(message_groups) == 0:
                break
            
            # Sort message groups by start_timestamp
            message_groups.sort(key=lambda x: x.metadata['start_timestamp'])

            # Extract and format page_content
            formatted_content = '\n\n'.join([group.page_content for group in message_groups])
            
            #print(formatted_content[:100])
            

            # Prepare prompt for LLM
            recent_profile_text = most_recent_profile.text if most_recent_profile else "No recent profile available"

            prompt = f"""
            Please create a profile of {user_name}. Their role is {user_role} and a brief bio is {user_bio}. 
            Here is the most recent profile of them: {recent_profile_text}
            Here are chat snippets involving this user since the most recent profile: {formatted_content}
            Please create an updated profile based on this information about the user.
            There is no need to include the user's role, name, or bio in the profile, as these are already separate fields, instead 
            focus on what can be learned about the user from the chat snippets. Please include the following sections in the profile:
            - general profile
            - personality
            - communication style
            - favorite words or phrases
            - work style
            - goals
            - values
            - strengths
            - weaknesses
            - relationships:
                - person 1
                - person 2
                ....etc
            """

            # Get updated profile from LLM
            response = await llm.ainvoke(prompt)
            updated_profile_text = response.content
            #print("response", response)
        
            # Store updated profile
            new_profile = UserProfile(
                user_id=user_id,
                profile_id=f'PROFILE#{datetime.now(timezone.utc).isoformat()}',
                text=updated_profile_text,
                last_message_timestamp_epoch=str(message_groups[-1].metadata['end_timestamp_epoch'])
            )
            self.store_user_profile(user_id, new_profile.to_dict())

            # Update most recent profile
            most_recent_profile = new_profile
            

        print(f"User profiles updated for user_id: {user_id}") 

    async def update_all_personas(self):
        """Update profiles for all users of type persona."""
        # Query to get all users of type persona
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#persona')
        )

        # Iterate over each persona user and update their profiles
        for item in response.get('Items', []):
            user_id = item['id']
            await self.update_user_profiles(user_id)

        print("All persona profiles updated.") 