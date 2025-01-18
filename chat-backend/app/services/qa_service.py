import json
import re
from typing import Dict, List, Optional, Tuple
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
import os
from datetime import datetime
import tiktoken

from .vector_service import VectorService
from .user_service import UserService
from .channel_service import ChannelService
from .message_service import MessageService
from .workspace_service import WorkspaceService
from ..models.message import Message

# Constants
TOKEN_LIMIT = 8192
BUFFER_SIZE = 250
MESSAGE_BATCH_SIZE = 5
PREVIOUS_MESSAGES_PREAMBLE = "The following is your previous answer, based on the previous relevant messages."
NEW_MESSAGES_PREAMBLE = "The following are the current messages. Please integrate the below set of messages with the previous response to provide a cohesive response. Avoid using words like \"continue\" and \"still\" that indicate you are comparing the previous response to the current messages. It should not be obvious to the end user that multiple prompts were used to construct the response."

class QAService:
    def __init__(self, table_name: str = None):
        """Initialize QA service with connections to other services"""
        self.vector_service = VectorService(table_name)
        self.user_service = UserService(table_name)
        self.channel_service = ChannelService(table_name)
        self.message_service = MessageService()
        self.workspace_service = WorkspaceService(table_name)
        # Initialize LangChain components
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        self.index_name = os.getenv("PINECONE_INDEX")
        self.llm = ChatOpenAI(temperature=0.7, model="gpt-4")
        
        # Define prompt templates
        self.user_template = PromptTemplate(
            template="""Based on the following context about a user, answer this question: {question}\nHere is recent chat history which may or may not be relevant to the current question:\n{recent_messages}\n\nContext about the user and their messages:\n{context}\n\nPlease provide a detailed answer based only on the information in the context.""",
            input_variables=["question", "context", "recent_messages"]
        )
        
        self.channel_template = PromptTemplate(
            template="""Based on the following context about a channel, answer this question: {question}\nHere is recent chat history which may or may not be relevant to the current question:\n{recent_messages}\n\nContext about the channel and its messages:\n{context}\n\nPlease provide a detailed answer based only on the information in the context.""",
            input_variables=["question", "context", "recent_messages"]
        )
        
        self.workspace_template = PromptTemplate(
            template="""Based on the following context about a workspace and its members, answer this question: {question}\nHere is recent chat history which may or may not be relevant to the current question:\n{recent_messages}\n\nContext about the workspace channels and users:\n{context}\n\nPlease provide a detailed answer based only on the information in the context.""",
            input_variables=["question", "context", "recent_messages"]
        )
        
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # Use the appropriate model
        
        # Initialize self.index in the constructor
        self.index = PineconeVectorStore(
            embedding=self.embeddings,
            index_name=self.vector_service.index_name
        )
    
    def count_tokens(self, text: str) -> int:
        tokens = self.tokenizer.encode(text)
        return len(tokens)

    async def _get_filtered_messages(self, question: str, filter_dict: dict, workspace_name: str) -> List:
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
        vector_store = self.index
        
        # Create retriever with enhanced parameters
        filtered_retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 10,  # Number of results to return
                "fetch_k": 100,  # Number of initial results to fetch before MMR
                "lambda_mult": 0.7,  # Increased from 0.5 to favor relevance over diversity
                "namespace": "grouped_messages",
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
        
        #retrieve the user profile from ddb
        user_profile = self.user_service.get_user_profile(user_id)
        return user_profile

    def _format_message(self, message: Message, channel_name: str = None) -> str:
        """Format a Message object with timestamp for context"""
        timestamp = message.created_at
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime("at: %Y/%m/%d %H:%M")
            except:
                timestamp = "at: unknown time"
        else:
            timestamp = "at: unknown time"

        # Get user name from service
        user_name = message.user.name if message.user else "Unknown User"

        if channel_name:
            return f"Message in {channel_name} from {user_name} {timestamp}:\n{message.content}"
        else:
            return f"{user_name}:\n{message.content}\n{timestamp}"


    def generate_initials(self, name: str, user_initials: dict) -> str:
        """Generate unique initials for a user name and store in user_initials."""
        if name in user_initials:
            return user_initials[name]
        parts = name.split()
        if len(parts) >= 2:
            initials = ''.join(p[0].upper() for p in parts)
        else:
            initials = name[:2].upper()
        base_initials = initials
        counter = 1
        while initials in user_initials.values():
            initials = f"{base_initials}{counter}"
            counter += 1
        user_initials[name] = initials
        return initials

    async def fetch_user_profiles(self, user_ids: set) -> dict:
        """Fetch user profiles for a set of user IDs."""
        user_profiles = {}
        for user_id in user_ids:
            profile = await self._get_user_profile(user_id)
            if profile:
                user_profiles[user_id] = profile
        return user_profiles

    async def build_context_parts(self, user_profiles: dict, message_docs: List[Message], channel_id_to_name: Dict[str, str]) -> Tuple:
        """Build context parts from user profiles and message documents."""
        context_parts = []
        user_initials = {}
        print("Formatting context parts...")
        if user_profiles:
            context_parts.append("Team Members:")
            for profile in user_profiles.values():
                content = profile.strip()
                name = content.split("\n")[0].replace("Name: ", "").strip()
                initials = self.generate_initials(name, user_initials)
                lines = content.split("\n")
                lines[0] = f"Name: {name}. Initials (for reference in chat): {initials}"
                context_parts.append(f"- {chr(10).join(lines)}")
        channel_messages = {}
        print("Building channel messages...")
        for message in message_docs:
            channel_id = message.channel_id
            channel_name = channel_id_to_name.get(channel_id, 'unknown-channel')
            if channel_id:
                if channel_id not in channel_messages:
                    channel_messages[channel_id] = {
                        'name': channel_name,
                        'messages': []
                    }
                channel_messages[channel_id]['messages'].append(message)
        sorted_channels = sorted(channel_messages.items(), key=lambda x: x[1]['name'])
        
        return context_parts, sorted_channels, user_initials

    def _add_message_to_context(self, message: Message, user_initials, current_date):
        """Add a single message to the context."""
        timestamp = message.created_at
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y/%m/%d")
                time_str = dt.strftime("%H:%M")
                if date_str != current_date:
                    current_date = date_str
                    timestamp_str = f"on {date_str} at {time_str}"
                else:
                    timestamp_str = f"at {time_str}"
            except:
                timestamp_str = "at unknown time"
        else:
            timestamp_str = "at unknown time"
        user_id = message.user_id
        try:
            user = self.user_service.get_user_by_id(user_id) if user_id else None
            user_name = user.name if user else "Unknown User"
            if user_name not in user_initials:
                user_initials[user_name] = self.generate_initials(user_name, user_initials)
            display_name = user_initials[user_name]
        except:
            display_name = "??"
        message_text = f"{display_name} {timestamp_str}:\n{message.content}"
        return message_text, current_date

    async def _add_message_channels_to_context(self, context_parts_before_messages, sorted_channels, user_initials, template, question, recent_messages="", start_channel=0, start_message=0):
        """Add messages from all channels to the context, starting from a specific channel and message index."""
        message_count = 0
        # Format the initial context with the template for accurate token counting
        initial_context = template.format(question=question, context="\n\n".join(context_parts_before_messages), recent_messages=recent_messages)
        total_tokens = self.count_tokens(initial_context)
        max_tokens = TOKEN_LIMIT - BUFFER_SIZE
        current_date = None
        context_parts = []
        context_parts.extend(context_parts_before_messages)
        context_parts.append("\nChannel Messages:")
        for channel_index, (channel_id, channel_data) in enumerate(sorted_channels[start_channel:], start=start_channel):
            channel_header = f"\n=== Messages from {channel_data['name']} ==="
            context_parts.append(channel_header)
            sorted_messages = sorted(channel_data['messages'], key=lambda message: message.created_at or '', reverse=False)
            current_date = None
            for message_index, message in enumerate(sorted_messages[start_message:] if channel_index == start_channel else sorted_messages, start=start_message if channel_index == start_channel else 0):
                message_text, current_date = self._add_message_to_context(message, user_initials, current_date)
                context_parts.append(message_text)
                message_count += 1
                if message_count % MESSAGE_BATCH_SIZE == 0 or message_index == len(sorted_messages) - 1:
                    updated_context = template.format(question=question, recent_messages=recent_messages, context="\n\n".join(context_parts))
                    total_tokens = self.count_tokens(updated_context)
                    if total_tokens > max_tokens:
                        print(f"\nReached token limit at {message_count} messages")
                        context_parts = context_parts[:-MESSAGE_BATCH_SIZE] # Remove the last batch of messages since it is over
                        message_index = max(0, message_index - MESSAGE_BATCH_SIZE) # Decrement message_index by MESSAGE_BATCH_SIZE to use these in the next call
                        return context_parts, channel_index, message_index + 1
                                        
            start_message = 0  # Reset start_message for subsequent channels
            if total_tokens > max_tokens:
                break
        print(f"✓ Included {message_count} messages (approx. {total_tokens} tokens)")
        return context_parts, None, None

    def _remove_duplicate_messages(self, message_docs: List[Message]) -> list:
        """Remove duplicate messages based on message_id or content hash."""
        seen_message_ids = set()
        unique_messages = []
        for message in message_docs:
            message_id = message.id
            if message_id and message_id not in seen_message_ids:
                seen_message_ids.add(message_id)
                unique_messages.append(message)
            elif not message_id:
                content_hash = hash(message.content)
                if content_hash not in seen_message_ids:
                    seen_message_ids.add(content_hash)
                    unique_messages.append(message)
        print(f"✓ Removed {len(message_docs) - len(unique_messages)} duplicate messages")
        return unique_messages

    def _convert_to_message(self, doc: Document ) -> Message:
        """Convert a document from the vector DB to a Message object."""
        
        return Message(
            id=doc.metadata.get('message_id'),
            content=doc.page_content,
            created_at=doc.metadata.get('timestamp'),
            user_id=doc.metadata.get('user_id'),
            channel_id=doc.metadata.get('channel_id')
        )

    async def _get_messages_from_vector_db(self, question: str, message_filter: dict, workspace_name: str) -> List[Message]:
        """Retrieve messages using the vector DB with semantic search and convert them to Message objects."""
        print(f"\nFetching messages with filter: {message_filter}")
        message_docs = await self._get_filtered_messages(question, message_filter, workspace_name)
        print(f"✓ Found {len(message_docs)} relevant messages")
        return [self._convert_to_message(doc) for doc in message_docs]

    async def _get_messages_from_ddb(self, channel_ids: List[str]) -> List:
        """Retrieve messages from DDB for given channel IDs."""
        message_docs = []
        for channel_id in channel_ids:
            print(f"Getting messages for channel {channel_id}")
            messages = self.message_service.get_messages(channel_id)
            message_docs.extend(messages)
        print(f"✓ Retrieved {len(message_docs)} messages from DDB")
        return message_docs

    async def _get_qa_response(
        self, 
        question: str,
        message_filter: dict,
        template: PromptTemplate,
        include_user_profiles: bool = True,
        additional_users: set = None,
        get_all: bool = False,
        workspace_name: str = None,
        recent_messages: str = ""
    ) -> Dict:
        """Core QA method used by all specific QA methods with a window-based approach."""
        if get_all:
            channel_ids = message_filter.get('channel_id', {}).get('$in', [])
            message_docs = await self._get_messages_from_ddb(channel_ids)
        else:
            message_docs = await self._get_messages_from_vector_db(question, message_filter, workspace_name)

        if not message_docs:
            return {
                "question": question,
                "answer": "No relevant messages found.",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Create a mapping from channel IDs to channel names
        channel_id_to_name = {channel_id: self.channel_service.get_channel_name_by_id(channel_id) for channel_id in message_filter.get('channel_id', {}).get('$in', [])}

        message_docs = self._remove_duplicate_messages(message_docs)
        message_user_ids = set(message.user_id for message in message_docs if message.user_id)
        user_ids = message_user_ids | (additional_users or set())
        print(f"\nFound {len(user_ids)} unique users")
        user_profiles = await self.fetch_user_profiles(user_ids) if include_user_profiles else {}

        context_parts_before_messages, sorted_channels, user_initials = await self.build_context_parts(user_profiles, message_docs, channel_id_to_name)

        responses = []
        start_channel = 0
        start_message = 0
        while True:
            print(f"Top of while loop, len of responses: {len(responses)}")
            if(len(responses) > 0):               
                context_parts_before_messages.append(f"{PREVIOUS_MESSAGES_PREAMBLE}{responses[-1]}")
                context_parts_before_messages.append(f"{NEW_MESSAGES_PREAMBLE}")
            context_parts, start_channel, start_message = await self._add_message_channels_to_context(context_parts_before_messages, sorted_channels, user_initials, template, question, recent_messages, start_channel, start_message)
            print("After add message channels to context")
            context = "\n\n".join(context_parts)
            print("About to format with recent messages: ", recent_messages)
            prompt = template.format(question=question, context=context, recent_messages=recent_messages)
            print(f"\n\n=== FULL PROMPT TOKENS: {self.count_tokens(prompt)}")
            os.makedirs("./temp", exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"./temp/qa_prompt_{timestamp}.txt"
                
            print("\nGetting answer from LLM...")
            response = await self.llm.ainvoke(prompt)
            print("✓ Got response")
            with open(filename, "a", encoding="utf-8") as f:
                f.write("=== QUESTION ===\n")
                f.write(question)
                f.write("\n\n=== FULL PROMPT ===\n")
                f.write(prompt)
                f.write("\n\n=== RESPONSE ===\n")
                f.write(response.content)
            responses.append(response.content)
            context_parts = ["Previous Response:", response.content] + context_parts
            print(f"\nWrote prompt and context to {filename}")
            if start_channel is None:
                break
        return {
            "question": question,
            "answer": responses[-1],
            "context_preview": context[:100] + "..." if len(context) > 100 else context,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def ask_about_channel(self, channel_id: str, question: str, get_all: bool = False) -> Dict:
        """Ask a question about a specific channel"""
        return await self._get_qa_response(
            question=question,
            message_filter={ "channel_id": {"$in": [channel_id]}},
            template=self.channel_template,
            get_all=get_all,
            workspace_name=self.channel_service.get_workspace_by_channel_id(channel_id).name
        )

    async def ask_about_workspace(self, workspace_id: str, question: str, get_all: bool = False, recent_messages: str = "") -> Dict:
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
        
        print(f"Workspace users: {workspace_users}")
        return await self._get_qa_response(
            question=question,
            message_filter={
                "channel_id": {"$in": [c.id for c in channels]}
            },
            template=self.workspace_template,
            additional_users=workspace_users,
            get_all=get_all,
            workspace_name=self.workspace_service.get_workspace_name_by_id(workspace_id),
            recent_messages=recent_messages
        )
        
    async def answer_bot_message(self, content: str, workspace_id: str, channel_id: str) -> Message:
        """Answer a message from the bot"""
        recent_messages = await self._get_recent_messages(channel_id)
        classification = await self._classify_query(content, recent_messages)
        print(f"Classification: {classification}")
        get_all = classification.get('type') == 'comprehensive'

        response = await self.ask_about_workspace(
            question=content,
            workspace_id=workspace_id,
            get_all=get_all,
            recent_messages=recent_messages
        )
        message = response.get("answer")
        print(f"Bot message: {message}")
        bot_user = self.user_service.get_bot_user("Bot")
        stored_message = self.message_service.create_message(
            content=message,
            channel_id=channel_id,
            user_id=bot_user.id
        )
        print(f"Stored message: {stored_message}")
        return stored_message
    
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
        
        # Prepare input
        input_text = f"User ID: {user_id}, Question: {question}"
        token_count = self.count_tokens(input_text)

        # Check token limit (e.g., 4096 for GPT-3)
        if token_count > 8192:
            raise ValueError("Input exceeds token limit!")

        return await self._get_qa_response(
            question=question,
            message_filter=message_filter,
            template=self.user_template,
            additional_users={user_id}
        ) 

    async def _get_recent_messages(self, channel_id: str) -> str:
        recent_messages = self.message_service.get_messages(channel_id, limit=11, reverse=True)[1:]
        recent_messages = recent_messages[::-1]  # Reverse to get oldest first
        return '\n'.join([msg.content for msg in recent_messages]) if recent_messages else 'N/A'

    async def _classify_query(self, content: str, recent_messages: str) -> Dict:
        # Prepare the question for OpenAI
        question = (
            "You are a query classifier that determines whether a user's question requires targeted message retrieval "
            "or comprehensive message analysis. Consider both the latest question and recent chat history when making your decision. "
            "Respond with a JSON object containing:\n\n"
            "1. 'type': Either 'targeted' or 'comprehensive'\n"
            "2. 'confidence': A score between 0 and 1\n"
            "3. 'reasoning': A brief explanation of your classification\n\n"
            "Guidelines:\n"
            "- 'targeted' questions typically:\n"
            "  * Focus on specific events, dates, or topics with clear boundaries\n"
            "  * Ask for straightforward factual information\n"
            "  * Show confidence in what they're looking for\n"
            "  * Can likely be answered with a small set of relevant messages\n\n"
            "- 'comprehensive' questions typically:\n"
            "  * Express uncertainty or skepticism about previous answers ('are you sure?', 'really?')\n"
            "  * Repetition or rephrasing of the same question may indicate a need for comprehensive analysis\n"
            "  * Ask about team dynamics, communication patterns, or organizational behavior\n"
            "  * Request analysis of sentiment, tone, or social interactions\n"
            "  * Explore how decisions or discussions evolved over time\n"
            "  * Look for implicit patterns that might not be captured in keyword searches\n"
            "  * Ask about general practices, team culture, or working styles\n"
            "  * Question the completeness or accuracy of information\n"
            "  * Require understanding of indirect or subtle contextual cues\n\n"
            "- Follow-up considerations:\n"
            "  * Questions expressing doubt should trigger comprehensive analysis\n"
            "  * Questions about broader impact or team implications need comprehensive review\n"
            "  * Simple clarifications about specific facts can remain targeted.  "
            "CHAT HISTORY:\n{recent_messages}\n\nCURRENT QUESTION: {question}"
        ).format(recent_messages=recent_messages, question=content)

        # Send the question to OpenAI
        response = await self.llm.ainvoke(question)
        print(f"Classify query response: {response.content}")
        
        #content is a string, so we need to convert it to a dictionary
        content = json.loads(response.content)
        print(f"Classify query response as dictionary: {content}")
        # Return the JSON response
        return content