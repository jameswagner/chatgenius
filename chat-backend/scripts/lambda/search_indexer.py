import os
import json
import boto3
import requests
from requests_aws4auth import AWS4Auth
import mimetypes
import textract
from io import BytesIO

# Configuration
REGION = os.environ['AWS_REGION']
HOST = os.environ['OPENSEARCH_ENDPOINT']
INDEX = 'messages'

# Initialize clients
s3 = boto3.client('s3')
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key,
                  REGION, 'es', session_token=credentials.token)

def extract_text_from_file(file_content, content_type):
    """Extract text from various file types"""
    try:
        # For text-based files, decode directly
        if content_type in ['text/plain', 'application/json', 'text/csv', 'application/xml']:
            return file_content.decode('utf-8')
        
        # For other supported files, use textract
        if content_type in ['application/pdf', 'application/msword', 
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return textract.process(file_content).decode('utf-8')
        
        return None
    except Exception as e:
        print(f"Error extracting text: {str(e)}")
        return None

def index_message(message_event):
    """Index a message and its attachments"""
    try:
        # Prepare the base document
        document = {
            'id': message_event['id'],
            'content': message_event['content'],
            'channel_id': message_event['channel_id'],
            'user_id': message_event['user_id'],
            'created_at': message_event['created_at'],
            'attachments': []
        }

        # Process attachments if any
        if 'attachments' in message_event and message_event['attachments']:
            for attachment in message_event['attachments']:
                # Get file from S3
                s3_response = s3.get_object(
                    Bucket=os.environ['ATTACHMENTS_BUCKET'],
                    Key=attachment
                )
                
                content_type = s3_response['ContentType']
                file_content = s3_response['Body'].read()
                
                # Extract text if it's a supported file type
                extracted_text = extract_text_from_file(file_content, content_type)
                
                if extracted_text:
                    document['attachments'].append({
                        'filename': attachment,
                        'content_type': content_type,
                        'content': extracted_text
                    })

        # Index the document
        url = f'https://{HOST}/{INDEX}/_doc/{document["id"]}'
        response = requests.put(url, auth=awsauth,
                              json=document,
                              headers={"Content-Type": "application/json"})
        
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to index document: {response.text}")
            
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Document indexed successfully'})
        }

    except Exception as e:
        print(f"Error indexing document: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def search_messages(event):
    """Search for messages based on query parameters"""
    try:
        params = event.get('queryStringParameters', {})
        query = params.get('q', '')
        channel_id = params.get('channel_id')
        user_id = params.get('user_id')
        
        # Build search query
        search_query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "content^2",  # Boost message content
                                    "attachments.content"
                                ]
                            }
                        }
                    ],
                    "filter": []
                }
            },
            "highlight": {
                "fields": {
                    "content": {},
                    "attachments.content": {}
                }
            }
        }
        
        # Add filters if specified
        if channel_id:
            search_query["query"]["bool"]["filter"].append({
                "term": {"channel_id": channel_id}
            })
        if user_id:
            search_query["query"]["bool"]["filter"].append({
                "term": {"user_id": user_id}
            })

        # Execute search
        url = f'https://{HOST}/{INDEX}/_search'
        response = requests.post(url, auth=awsauth,
                               json=search_query,
                               headers={"Content-Type": "application/json"})
        
        if response.status_code != 200:
            raise Exception(f"Search failed: {response.text}")
            
        return {
            'statusCode': 200,
            'body': json.dumps(response.json())
        }

    except Exception as e:
        print(f"Error searching documents: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        # Determine the operation based on the event
        if event.get('httpMethod') == 'GET':
            return search_messages(event)
        else:
            # Assume it's an indexing event
            return index_message(json.loads(event['body']))
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        } 