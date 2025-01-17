import re
from typing import List, Dict, Optional, Literal
import os
from datetime import datetime, timedelta
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from .message_service import MessageService
from .channel_service import ChannelService
from .workspace_service import WorkspaceService
from .user_service import UserService
from ..models.channel import Channel
from ..models.message import Message
from ..models.workspace import Workspace
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec


# Load environment variables
load_dotenv()

MESSAGES_PER_VECTOR = 10

class VectorService:
    def __init__(self, table_name: str = None):
        """Initialize vector service with connections to other services and Pinecone"""
        self.message_service = MessageService(table_name)
        self.channel_service = ChannelService(table_name)
        self.user_service = UserService(table_name)
        self.workspace_service = WorkspaceService(table_name)
        
        # Initialize embedding model with explicit API key
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large",
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        self.index_name = os.getenv("PINECONE_INDEX")
        self.pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        os.environ["PINECONE_API_KEY"] = os.getenv("PINECONE_API_KEY")
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
            "workspace_name": channel.workspace_name if channel else "NO_WORKSPACE",
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

    async def index_workspace(self, workspace_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, is_grouped: bool = False):
        """Index all channels in a workspace"""
        
        workspace_name = self.workspace_service.get_workspace_name_by_id(workspace_id)
        print(f"Indexing workspace {workspace_name}")
        if not workspace_name:
            raise ValueError(f"Workspace {workspace_id} not found")

        # Get all channels in the workspace
        channels = self.channel_service.get_workspace_channels(workspace_id)
        print(f"Found {len(channels)} channels in workspace {workspace_name}")
        for channel in channels:
            await self.index_channel(channel.id, start_date, end_date, is_grouped)

    async def index_channel(self, channel_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, is_grouped: bool = False) -> int:
        """Index all messages in a channel"""
        channel = self.channel_service.get_channel_by_id(channel_id)
        workspace = self.workspace_service.get_workspace_by_id(channel.workspace_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        # Convert dates to strings
        start_time = start_date.isoformat() if start_date else None
        if end_date:
            end_date = end_date + timedelta(days=1) - timedelta(seconds=1)  # Set to end of the day
        end_time = end_date.isoformat() if end_date else None

        # Check if index exists, create if not
        index_name = f"{self.index_name}-{workspace.name}".lower()
        # replace non alphanumeric characters with '-'
        index_name = re.sub(r'[^a-z0-9]+', '-', index_name)
        indices = self.pinecone.list_indexes()
        index_names = [index.name for index in indices]
        print(f"Index names: {index_names}")
        if index_name not in index_names:
            print(f"Creating index {index_name}")
            self.pinecone.create_index(index_name, dimension=3072, spec=ServerlessSpec(cloud='aws', region='us-east-1') 
)
            print(f"Created index {index_name}")

        # Get messages
        messages = self.message_service.get_messages(channel_id, start_time=start_time, end_time=end_time)
        if not messages:
            return 0

        if not is_grouped:
            # Prepare metadata
            for message in messages:
                metadata = self._prepare_message_metadata(message, channel.name)
                # Index message
                self.index.upsert(index_name, message.id, message.content, metadata)
        else:
            await self.index_grouped_messages(channel_id, messages, index_name, workspace)

        return len(messages)

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

    async def index_grouped_messages(self, channel_id: str, messages: List[Message], index_name: str, workspace: Workspace) -> int:
        """Index messages in groups based on MESSAGES_PER_VECTOR and threads"""
        print(f"Indexing grouped messages for channel {channel_id}")
        channel = self.channel_service.get_channel_by_id(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")
        
        message_id_to_message = {message.id: message for message in messages}
        index = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=index_name
        )
        grouped_messages = []
        for message in messages:
            if message.thread_id:
                continue # thread messages are handled separately
            # Start a new vector if we reach the limit or encounter a thread
            if len(grouped_messages) >= MESSAGES_PER_VECTOR or (len(grouped_messages) > 0 and message.reply_count > 0):
                await self._store_group_vector(grouped_messages, channel, workspace, index)
                grouped_messages = []

            grouped_messages.append(message)

            # Handle threads separately
            if message.reply_count > 0:
                for reply_id in message.replies:
                    reply_message = message_id_to_message.get(reply_id)
                    if reply_message:
                        grouped_messages.append(reply_message)
                    if len(grouped_messages) >= MESSAGES_PER_VECTOR:
                        await self._store_group_vector(grouped_messages, channel, workspace, index, message.id)
                        grouped_messages = []
                if len(grouped_messages) > 0: # store the last group
                    await self._store_group_vector(grouped_messages, channel, workspace, index, message.id)
                    grouped_messages = []

        # Store any remaining messages
        if grouped_messages:
            await self._store_group_vector(grouped_messages, channel, workspace, index)

        return len(messages)

    async def _store_group_vector(self, messages: List[Message], channel: Channel, workspace: Workspace, index: PineconeVectorStore, thread_id: Optional[str] = None):
        """Store a group of messages as a vector"""
        if not messages:
            return

        # Ensure created_at is a datetime object
        for msg in messages:
            if isinstance(msg.created_at, str):
                msg.created_at = datetime.fromisoformat(msg.created_at)

        # Prepare metadata
        metadata = {
            "vector_type": "thread_message" if thread_id else "grouped_message",
            "message_count": len(messages),
            "start_timestamp": messages[0].created_at,
            "end_timestamp": messages[-1].created_at,
            "thread_id": thread_id if thread_id else "",
            "channel_id": channel.id,
            "channel_name": channel.name,
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "message_ids": [msg.id for msg in messages],
            "user_ids": list(set(msg.user_id for msg in messages))
        }

        # Concatenate message contents with sender and concise timestamp
        content = "\n".join([
            f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.user.name}: {msg.content}"
            for msg in messages
        ])
        
        
        if thread_id:
            print(f"Thread ID: {thread_id}")
            print(f"Metadata: {metadata}")
            print(f"Messages: {messages}")

        # Index the vector
        await index.aadd_texts([content], [metadata], namespace="grouped_messages")
        

    async def lookup_message_group_by_message_id(self, message_id: str) -> Optional[Dict]:
        """Lookup a message group by a message ID"""
        results = self.index.similarity_search(
            query="",
            filter={"message_ids": message_id},
            k=1
        )
        return results[0] if results else None

    async def lookup_message_group_by_user_id(self, user_id: str) -> List[Dict]:
        """Lookup message groups by a user ID"""
        results = self.index.similarity_search(
            query="",
            filter={"user_ids": user_id},
            k=10
        )
        return results 

    async def index_all_workspaces(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, is_grouped: bool = False):
        """Index all workspaces with optional start and end dates"""
        workspaces = self.workspace_service.get_all_workspaces()
        for workspace in workspaces:
            await self.index_workspace(workspace.id, start_date, end_date, is_grouped) 