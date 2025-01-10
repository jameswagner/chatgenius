import pytest
import subprocess
import time
import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import boto3
from botocore.exceptions import ClientError
from app.db.ddb import DynamoDB

@pytest.fixture
def test_db():
    """Create a new database for testing"""
    return DynamoDB(table_name='chat_app_jrw_test')

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Set environment variable before importing main
    import os
    os.environ['DYNAMODB_TABLE'] = 'chat_app_jrw_test'
    
    # Create the Flask app
    import main
    main.app.config.update({
        'TESTING': True
    })
    
    # Create a test client
    with main.app.test_client() as client:
        with main.app.app_context():
            yield main
            
    # Clean up test table items after tests
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('chat_app_jrw_test')
    
    # Scan and delete all items
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan['Items']:
            batch.delete_item(
                Key={
                    'PK': item['PK'],
                    'SK': item['SK']
                }
            )

@pytest.fixture(scope="session")
def react_server():
    """Start the React development server for testing"""
    import os
    
    # Get absolute path to frontend directory
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_dir = os.path.join(os.path.dirname(backend_dir), "chat-frontend")
    
    # Start the React server with test configuration
    process = subprocess.Popen(
        "npm run dev:test",
        cwd=frontend_dir,
        shell=True,  # Use shell to ensure npm is found
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give the server time to start
    time.sleep(5)  # Adjust if needed
    
    yield process
    
    # Cleanup: terminate the server
    process.terminate()
    process.wait()

@pytest.fixture
def driver(react_server):
    """Provide a selenium webdriver instance"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    
    # Use selenium-manager instead of ChromeDriverManager
    driver = webdriver.Chrome(options=options)
    
    yield driver
    
    driver.quit()

@pytest.fixture
def second_driver(react_server):
    """Provide a second selenium webdriver instance for multi-user testing"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    
    # Use selenium-manager instead of ChromeDriverManager
    driver = webdriver.Chrome(options=options)
    
    yield driver
    
    driver.quit() 