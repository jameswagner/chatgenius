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
        
        # Initialize retriever with MMR search for better diversity
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 1000,  # Increased from 200
                "fetch_k": 1500,  # Increased from 100
                "lambda_mult": 0.5,  # Diversity factor
                "namespace": "messages"  # Add namespace to match where documents are stored
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
        
        self.workspace_template = PromptTemplate(
            template="""Based on the following context about a workspace and its members, answer this question: {question}

Context about the workspace channels and users:
{context}

Please provide a detailed answer based only on the information in the context.""",
            input_variables=["question", "context"]
        )
    
    async def _get_filtered_messages(self, question: str, filter_dict: dict) -> List:
        """Get messages using a filtered retriever with semantic search"""
        # Enhance the question to better capture the topic
        search_query = f"""
        Find messages related to: {question}
        Look for:
        - Direct mentions of these topics
        - Related discussions
        - Relevant context
        - Supporting details
        """
        
        # Create retriever with enhanced parameters
        filtered_retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 1000,  # Number of results to return
                "fetch_k": 1500,  # Number of initial results to fetch before MMR
                "lambda_mult": 0.7,  # Increased from 0.5 to favor relevance over diversity
                "namespace": "messages",
                "filter": filter_dict,
                "score_threshold": 0.7  # Only return results with cosine similarity above this
            }
        )
        
        print(f"\nSearching with enhanced query for topic: {question}")
        results = await filtered_retriever.ainvoke(search_query)
        print(f"Found {len(results)} semantically relevant messages")
        return results

    async def _get_user_profile(self, user_id: str) -> Optional[dict]:
        """Get a user's profile from vector store"""
        profile_retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 1,
                "namespace": "users",
                "filter": {"type": "user_profile", "user_id": user_id}
            }
        )
        results = await profile_retriever.ainvoke("")
        return results[0] if results else None

    def _format_message(self, doc: dict, channel_name: str = None) -> str:
        """Format a message with timestamp for context"""
        timestamp = doc.metadata.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime("at: %Y/%m/%d %H:%M")
            except:
                timestamp = "at: unknown time"
        else:
            timestamp = "at: unknown time"

        # Get user name from service
        user_id = doc.metadata.get('user_id')
        try:
            user = self.user_service.get_user_by_id(user_id) if user_id else None
            user_name = user.name if user else "Unknown User"
        except:
            user_name = "Unknown User"

        if channel_name:
            return f"Message in {channel_name} from {user_name} {timestamp}:\n{doc.page_content}"
        else:
            return f"{user_name}:\n{doc.page_content}\n{timestamp}"

    def _format_user_profile(self, profile_doc: dict) -> str:
        """Format a user profile for context"""
        return f"- {profile_doc.page_content.strip()}"

    async def _get_qa_response(
        self, 
        question: str,
        message_filter: dict,
        template: PromptTemplate,
        include_user_profiles: bool = True,
        additional_users: set = None
    ) -> Dict:
        """Core QA method used by all specific QA methods"""
        # Get messages
        print(f"\nFetching messages with filter: {message_filter}")
        message_docs = await self._get_filtered_messages(question, message_filter)
        print(f"✓ Found {len(message_docs)} relevant messages")
        
        if not message_docs:
            return {
                "question": question,
                "answer": "No relevant messages found in the vector store.",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Remove duplicates by message_id
        seen_message_ids = set()
        unique_messages = []
        for doc in message_docs:
            message_id = doc.metadata.get('message_id')
            if message_id and message_id not in seen_message_ids:
                seen_message_ids.add(message_id)
                unique_messages.append(doc)
            elif not message_id:
                # If no message_id, use content as fallback for deduplication
                content_hash = hash(doc.page_content)
                if content_hash not in seen_message_ids:
                    seen_message_ids.add(content_hash)
                    unique_messages.append(doc)
        
        print(f"✓ Removed {len(message_docs) - len(unique_messages)} duplicate messages")
        message_docs = unique_messages
        
        # Get unique users from messages
        message_user_ids = set(doc.metadata.get('user_id') for doc in message_docs if doc.metadata.get('user_id'))
        user_ids = message_user_ids | (additional_users or set())
        print(f"\nFound {len(user_ids)} unique users")
        
        # Get user profiles if needed
        user_profiles = {}
        if include_user_profiles:
            print("\nFetching user profiles...")
            for user_id in user_ids:
                profile = await self._get_user_profile(user_id)
                if profile:
                    print(f"✓ Found profile for {user_id}")
                    user_profiles[user_id] = profile
                else:
                    print(f"✗ No profile found for {user_id}")
        
        # Build context
        print("\nBuilding context...")
        context_parts = []
        
        # Create initials mapping for users
        user_initials = {}
        seen_initials = set()
        
        def generate_initials(name: str) -> str:
            # Split name and get first letter of each part
            parts = name.split()
            if len(parts) >= 2:
                initials = ''.join(p[0].upper() for p in parts)
            else:
                # If single name, use first two letters
                initials = name[:2].upper()
            
            # If initials already seen, add numbers until unique
            base_initials = initials
            counter = 1
            while initials in seen_initials:
                initials = f"{base_initials}{counter}"
                counter += 1
            
            seen_initials.add(initials)
            return initials
        
        # Add user profiles with initials
        if user_profiles:
            context_parts.append("Team Members:")
            for profile in user_profiles.values():
                # Extract user name from profile content
                content = profile.page_content.strip()
                if content.startswith("Name: "):
                    name = content.split("\n")[0].replace("Name: ", "").strip()
                    initials = generate_initials(name)
                    user_initials[name] = initials
                    # Add initials to profile
                    lines = content.split("\n")
                    lines[0] = f"Name: {name} ({initials})"
                    context_parts.append(f"- {chr(10).join(lines)}")
                else:
                    context_parts.append(self._format_user_profile(profile))
        
        # Group messages by channel
        channel_messages = {}
        for doc in message_docs:
            channel_id = doc.metadata.get('channel_id')
            channel_name = doc.metadata.get('channel_name', 'unknown-channel')
            if channel_id:
                if channel_id not in channel_messages:
                    channel_messages[channel_id] = {
                        'name': channel_name,
                        'messages': []
                    }
                channel_messages[channel_id]['messages'].append(doc)

        # Sort channels by name for consistent ordering
        sorted_channels = sorted(channel_messages.items(), key=lambda x: x[1]['name'])
        
        # Add messages channel by channel
        context_parts.append("\nChannel Messages:")
        message_count = 0
        total_tokens = sum(len(part.split()) for part in context_parts)
        max_tokens = 14000
        current_date = None
        
        for channel_id, channel_data in sorted_channels:
            # Add channel header
            channel_header = f"\n=== Messages from {channel_data['name']} ==="
            context_parts.append(channel_header)
            
            # Sort messages within channel
            sorted_messages = sorted(
                channel_data['messages'],
                key=lambda doc: doc.metadata.get('timestamp', ''),
                reverse=False
            )
            
            # Reset current_date for each channel
            current_date = None
            
            # Add messages from this channel
            for doc in sorted_messages:
                # Get timestamp
                timestamp = doc.metadata.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_str = dt.strftime("%Y/%m/%d")
                        time_str = dt.strftime("%H:%M")
                        
                        # If date changed or first message, include full date
                        if date_str != current_date:
                            current_date = date_str
                            timestamp_str = f"on {date_str} at {time_str}"
                        else:
                            timestamp_str = f"at {time_str}"
                    except:
                        timestamp_str = "at unknown time"
                else:
                    timestamp_str = "at unknown time"
                
                # Get user name and initials
                user_id = doc.metadata.get('user_id')
                try:
                    user = self.user_service.get_user_by_id(user_id) if user_id else None
                    user_name = user.name if user else "Unknown User"
                    # Get or generate initials
                    if user_name not in user_initials:
                        user_initials[user_name] = generate_initials(user_name)
                    display_name = user_initials[user_name]
                except:
                    display_name = "??"
                
                # Format message
                message_text = f"{display_name} {timestamp_str}:\n{doc.page_content}"
                message_tokens = len(message_text.split()) + 10
                
                if total_tokens + message_tokens > max_tokens:
                    print(f"\nReached token limit at {message_count} messages")
                    break
                    
                context_parts.append(message_text)
                total_tokens += message_tokens
                message_count += 1
            
            # Break outer loop if we hit token limit
            if total_tokens > max_tokens:
                break
        
        print(f"✓ Included {message_count} messages (approx. {total_tokens} tokens)")
        
        # Get answer
        context = "\n\n".join(context_parts)
        prompt = template.format(
            question=question,
            context=context
        )
        
        # Write prompt and context to file
        os.makedirs("./temp", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"./temp/qa_prompt_{timestamp}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("=== QUESTION ===\n")
            f.write(question)
            f.write("\n\n=== CONTEXT ===\n")
            f.write(context)
            f.write("\n\n=== FULL PROMPT ===\n")
            f.write(prompt)
        print(f"\nWrote prompt and context to {filename}")
        
        print("\nGetting answer from LLM...")
        response = await self.llm.ainvoke(prompt)
        print("✓ Got response")
        
        return {
            "question": question,
            "answer": response.content,
            "context_preview": context[:100] + "..." if len(context) > 100 else context,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def ask_about_channel(self, channel_id: str, question: str) -> Dict:
        """Ask a question about a specific channel"""
        return await self._get_qa_response(
            question=question,
            message_filter={"type": "message", "channel_id": channel_id},
            template=self.channel_template
        )

    async def ask_about_workspace(self, workspace_id: str, question: str) -> Dict:
        """Answer questions about a workspace using context from its channels and users"""
        # Get all channels in workspace
        print(f"\n=== Starting workspace QA for '{workspace_id}' ===")
        channels = self.channel_service.get_workspace_channels(workspace_id)
        if not channels:
            raise ValueError(f"No channels found in workspace '{workspace_id}'")
        print(f"✓ Found {len(channels)} channels")
        
        # Get all channel members
        workspace_users = set()
        for channel in channels:
            members = self.channel_service.get_channel_members(channel.id)
            workspace_users.update(member['id'] for member in members)
        
        return await self._get_qa_response(
            question=question,
            message_filter={
                "type": "message",
                "channel_id": {"$in": [c.id for c in channels]}
            },
            template=self.workspace_template,
            additional_users=workspace_users
        )

    async def ask_about_user(self, user_id: str, question: str, include_channel_context: bool = False) -> Dict:
        """Ask a question about a specific user"""
        if include_channel_context:
            # Get channels the user is a member of
            channels = self.channel_service.get_channels_for_user(user_id)
            channel_ids = [channel.id for channel in channels]
            message_filter = {
                "$or": [
                    {"type": "message", "user_id": user_id},
                    {"type": "message", "channel_id": {"$in": channel_ids}}
                ]
            }
        else:
            message_filter = {"type": "message", "user_id": user_id}
        
        return await self._get_qa_response(
            question=question,
            message_filter=message_filter,
            template=self.user_template,
            additional_users={user_id}
        ) 