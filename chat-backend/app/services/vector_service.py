from typing import List, Dict, Optional, Literal
import os
from datetime import datetime
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from .message_service import MessageService
from .channel_service import ChannelService
from .user_service import UserService
from ..models.message import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VectorService:
    def __init__(self, table_name: str = None):
        """Initialize vector service with connections to other services and Pinecone"""
        self.message_service = MessageService(table_name)
        self.channel_service = ChannelService(table_name)
        self.user_service = UserService(table_name)
        
        # Initialize embedding model with explicit API key
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        self.index_name = os.getenv("PINECONE_INDEX")
        print(f"Index name: {self.index_name}")
        
        # Initialize Pinecone vector store
        self.index = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=self.index_name
        )
        
        # Text splitter for long messages
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        
    def _prepare_message_metadata(self, message: Message, channel_name: str) -> Dict:
        """Prepare metadata for a message"""
        # Get user for name
        user = self.user_service.get_user_by_id(message.user_id)
        
        # Get channel for workspace
        channel = self.channel_service.get_channel_by_id(message.channel_id)
        
        metadata = {
            "type": "message",  # Identify this as a message embedding
            "message_id": message.id,
            "channel_id": message.channel_id,
            "channel_name": channel_name,
            "user_id": message.user_id,
            "user_name": user.name if user else "Unknown User",
            "workspace_id": channel.workspace_id if channel else "NO_WORKSPACE",
            "timestamp": message.created_at,
            "is_reply": bool(message.thread_id),
            "message_type": "thread_reply" if message.thread_id else "channel_message"
        }
        
        # Only add thread_id if it exists
        if message.thread_id:
            metadata["thread_id"] = message.thread_id
            
        return metadata
        
    def _prepare_user_metadata(self, user) -> Dict:
        """Prepare metadata for a user profile"""
        return {
            "type": "user_profile",  # Identify this as a user profile embedding
            "user_id": user.id,
            "user_name": user.name,
            "user_type": user.type,
            "user_role": user.role,
            "last_updated": datetime.utcnow().isoformat()
        }

    async def index_channel(self, channel_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
        """Index all messages in a channel
        
        Args:
            channel_id: The channel to index
            start_date: Only index messages after this date
            end_date: Only index messages before this date
            
        Returns:
            Number of messages indexed
        """
        # Get channel
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")
        
        # Get messages
        messages = self.message_service.get_messages(channel_id)
        if not messages:
            print(f"No messages found in channel {channel.name}")
            return 0
        
        print(f"Found {len(messages)} messages in channel {channel.name}")
        
        # Filter messages by date if specified
        if start_date or end_date:
            filtered_messages = []
            for msg in messages:
                msg_date = datetime.fromisoformat(msg.created_at)
                if start_date and msg_date < start_date:
                    continue
                if end_date and msg_date > end_date:
                    continue
                filtered_messages.append(msg)
            messages = filtered_messages
            print(f"After date filtering: {len(messages)} messages")
        
        # Prepare texts and metadata for batch indexing
        texts = []
        metadatas = []
        
        for message in messages:
            try:
                # Get user for metadata
                user = self.user_service.get_user_by_id(message.user_id)
                if not user:
                    print(f"User {message.user_id} not found for message {message.id}")
                    continue
                    
                # Prepare metadata
                metadata = self._prepare_message_metadata(message, channel.name)
                
                # Add to batch
                texts.append(message.content)
                metadatas.append(metadata)
                
            except Exception as e:
                print(f"Error preparing message {message.id}: {str(e)}")
                continue
        
        if not texts:
            print("No valid messages to index")
            return 0
            
        try:
            # Batch index in Pinecone
            await self.index.aadd_texts(
                texts=texts,
                metadatas=metadatas,
                namespace="messages"
            )
            print(f"Successfully indexed {len(texts)} messages from channel {channel.name}")
            return len(texts)
        except Exception as e:
            print(f"Error batch indexing messages: {str(e)}")
            return 0
        
    async def index_user(self, user_id: str) -> bool:
        """Index a user's profile information
        
        Args:
            user_id: The user to index
            
        Returns:
            True if successful
        """
        # Get user
        user = self.user_service.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        try:
            # Create profile text
            profile_text = f"Name: {user.name}\nRole: {user.role}\nBio: {user.bio}"
            
            # Prepare metadata
            metadata = self._prepare_user_metadata(user)
            
            # Index in Pinecone using aadd_texts
            await self.index.aadd_texts(
                texts=[profile_text],
                metadatas=[metadata],
                namespace="users"
            )
            
            print(f"Successfully indexed profile for user {user.name}")
            return True
            
        except Exception as e:
            print(f"Error indexing user {user_id}: {str(e)}")
            return False
        
    async def search_similar(
        self, 
        query: str, 
        doc_type: Literal["message", "user_profile", "all"] = "all",
        limit: int = 10
    ) -> List[Dict]:
        """Search for similar content across messages and/or user profiles
        
        Args:
            query: The search query
            doc_type: Type of documents to search ("message", "user_profile", or "all")
            limit: Maximum number of results
            
        Returns:
            List of relevant documents with metadata
        """
        vector_store = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=self.index_name
        )
        
        # Set up type filter if not searching all
        filter_dict = {}
        if doc_type != "all":
            filter_dict["type"] = doc_type
            
        results = vector_store.similarity_search(
            query=query,
            filter=filter_dict if filter_dict else None,
            k=limit
        )
        
        return [{
            "content": doc.page_content,
            "metadata": doc.metadata,
            "type": doc.metadata.get("type", "unknown")
        } for doc in results]
        
    async def get_user_context(self, user_id: str, include_profile: bool = True) -> Dict:
        """Get a user's context including their profile and recent messages
        
        Args:
            user_id: The user to get context for
            include_profile: Whether to include the user's profile embedding
            
        Returns:
            Dict with user profile and messages
        """
        vector_store = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=self.index_name
        )
        
        # Get user profile if requested
        profile = None
        if include_profile:
            profile_results = vector_store.similarity_search(
                query="",
                filter={"type": "user_profile", "user_id": user_id},
                k=1
            )
            if profile_results:
                profile = {
                    "content": profile_results[0].page_content,
                    "metadata": profile_results[0].metadata
                }
        
        # Get user's messages
        message_results = vector_store.similarity_search(
            query="",
            filter={"type": "message", "user_id": user_id},
            k=100
        )
        
        messages = [{
            "content": doc.page_content,
            "metadata": doc.metadata
        } for doc in message_results]
        
        return {
            "profile": profile,
            "messages": messages,
            "user_id": user_id
        } 