from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain_pinecone import PineconeVectorStore
import os
from datetime import datetime

from .vector_service import VectorService
from .user_service import UserService
from .channel_service import ChannelService

class QAService:
    def __init__(self, table_name: str = None):
        """Initialize QA service with connections to other services"""
        self.vector_service = VectorService(table_name)
        self.user_service = UserService(table_name)
        self.channel_service = ChannelService(table_name)
        
        # Initialize LangChain components
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        self.index_name = os.getenv("PINECONE_INDEX")
        self.llm = ChatOpenAI(temperature=0.7, model="gpt-4")
        
        # Initialize vector store
        self.vector_store = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=self.index_name
        )
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={
                "k": 100,  
                "filter": {}  # Will be overridden in calls
            }
        )
        
        # Define prompt templates
        self.user_template = PromptTemplate(
            template="""Based on the following context about a user, answer this question: {question}

Context about the user and their messages:
{context}

Please provide a detailed answer based only on the information in the context.""",
            input_variables=["question", "context"]
        )
        
        self.channel_template = PromptTemplate(
            template="""Based on the following context about a channel, answer this question: {question}

Context about the channel and its messages:
{context}

Please provide a detailed answer based only on the information in the context.""",
            input_variables=["question", "context"]
        )
    
    async def ask_about_user(self, user_id: str, question: str, include_channel_context: bool = False) -> Dict:
        """Ask a question about a specific user
        
        Args:
            user_id: The user to ask about
            question: The question to ask
            include_channel_context: If True, includes messages from channels where user participates
            
        Returns:
            Dict with the answer and relevant context
        """
        # Get user's own messages from vector store
        filter_dict = {"type": "message", "user_id": user_id}
        user_messages = await self.retriever.ainvoke(
            question,
            {"filter": filter_dict}
        )
        
        # Get user profile
        profile_filter = {"type": "user_profile", "user_id": user_id}
        profile_docs = await self.retriever.ainvoke(
            "",  # Empty query to get profile
            {"filter": profile_filter}
        )
        
        context_parts = []
        
        # Add user profile if found
        if profile_docs:
            context_parts.append("User Profile:")
            context_parts.append(profile_docs[0].page_content)
        
        # Add user's messages
        context_parts.append("\nUser's Messages:")
        for doc in user_messages:
            context_parts.append(
                f"Message: {doc.page_content}\n"
                f"Timestamp: {doc.metadata.get('timestamp')}"
            )
            
        # Optionally get channel context
        channel_messages = []
        if include_channel_context:
            # Get channels the user is a member of
            channels = self.channel_service.get_channels_for_user(user_id)
            
            context_parts.append("\nChannel Context:")
            for channel in channels:
                channel_filter = {
                    "type": "message",
                    "channel_id": channel.id,
                }
                channel_docs = await self.retriever.ainvoke(
                    question,
                    {"filter": channel_filter}
                )
                
                if channel_docs:
                    context_parts.append(f"\nMessages from channel {channel.name}:")
                    for doc in channel_docs[:10]:  # Limit to 10 most relevant messages per channel
                        if doc.metadata.get('user_id') != user_id:  # Skip user's own messages to avoid duplication
                            context_parts.append(
                                f"From {doc.metadata.get('user_name', 'Unknown')}:\n"
                                f"{doc.page_content}\n"
                                f"Timestamp: {doc.metadata.get('timestamp')}"
                            )
                            channel_messages.append(doc)
        
        # Format context for prompt
        context_str = "\n\n".join(context_parts)
        
        # Generate prompt with context
        prompt = self.user_template.format(
            question=question,
            context=context_str
        )
        
        # Get answer from LLM
        response = await self.llm.ainvoke(prompt)
        
        return {
            "question": question,
            "answer": response.content,
            "context": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in (user_messages + profile_docs + channel_messages)
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def ask_about_channel(self, channel_id: str, question: str) -> Dict:
        """Ask a question about a specific channel"""
        # Get channel context from vector store
        message_filter = {"type": "message", "channel_id": channel_id}
        print(f"\n=== Retrieving messages for channel {channel_id} ===")
        print(f"Filter: {message_filter}")
        message_docs = await self.retriever.ainvoke(
            question,
            {"filter": message_filter}
        )
        print(f"Retrieved {len(message_docs)} messages")
        
        # Get unique user IDs from messages
        user_ids = set(doc.metadata.get('user_id') for doc in message_docs)
        print(f"\nFound {len(user_ids)} unique users in messages:")
        print(f"User IDs: {user_ids}")
        
        # Get user profiles for all users in the conversation
        user_profiles = {}
        print("\nRetrieving user profiles:")
        for user_id in user_ids:
            profile_filter = {"type": "user_profile", "user_id": user_id}
            print(f"\nLooking up profile for user {user_id}")
            print(f"Filter: {profile_filter}")
            profile_docs = await self.retriever.ainvoke(
                "",  # Empty query to get profile
                {"filter": profile_filter}
            )
            if profile_docs:
                print(f"✓ Found profile")
                user_profiles[user_id] = profile_docs[0]
            else:
                print(f"✗ No profile found")
        
        print(f"\nFound {len(user_profiles)} user profiles")
        
        # Format context for prompt, including user profiles
        context_parts = []
        
        # First add user profiles
        context_parts.append("Team Members:")
        for user_id, profile in user_profiles.items():
            context_parts.append(f"- {profile.page_content}")
        
        # Then add relevant messages
        context_parts.append("\nConversation:")
        message_count = 0
        print("\nProcessing messages:")
        for doc in message_docs:
            user_id = doc.metadata.get('user_id')
            user_profile = user_profiles.get(user_id)
            print(f"\nMessage from user_id: {user_id}")
            print(f"User profile metadata: {user_profile.metadata if user_profile else 'No profile'}")
            print(f"User profile content: {user_profile.page_content if user_profile else 'No profile'}")
            
            # Get user name from profile content instead of metadata
            if user_profile:
                # Extract name from the profile content which should be in format "Name: {name}\nRole: ..."
                name_line = user_profile.page_content.split('\n')[0].strip()
                user_name = name_line.replace('Name:', '').strip()
            else:
                user_name = 'Unknown'
                
            print(f"Extracted user name: {user_name}")
            
            context_parts.append(
                f"Message from {user_name}:\n"
                f"{doc.page_content}\n"
                f"Timestamp: {doc.metadata.get('timestamp')}"
            )
            message_count += 1
        
        print(f"\nIncluded {message_count} messages in context")
        print(f"From {len(user_profiles)} users")
        
        context_str = "\n\n".join(context_parts)
        
        # Update channel template to better handle the structured context
        channel_template = PromptTemplate(
            template="""Based on the following context about a channel and its team members, answer this question: {question}

{context}

Please provide a detailed answer that takes into account both the team members' roles/backgrounds and their messages in the channel.
Focus on connecting what people say with their roles and expertise when relevant.""",
            input_variables=["question", "context"]
        )
        
        # Generate prompt with enhanced context
        prompt = channel_template.format(
            question=question,
            context=context_str
        )
        
        print("\n=== PROMPT SENT TO LLM ===")
        print(prompt)
        print("=== END PROMPT ===\n")
        
        # Get answer from LLM
        response = await self.llm.ainvoke(prompt)
        
        print("\n=== LLM RESPONSE ===")
        print(response.content)
        print("=== END RESPONSE ===\n")
        
        return {
            "question": question,
            "answer": response.content,
            "context": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in message_docs + list(user_profiles.values())
            ],
            "timestamp": datetime.utcnow().isoformat()
        } 