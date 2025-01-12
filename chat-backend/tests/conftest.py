import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from app.db.ddb import DynamoDB
import subprocess
import time
import os
import requests
from pathlib import Path
import sys
from selenium.webdriver.firefox.options import Options as FirefoxOptions

# @pytest.fixture(scope="session", autouse=True)
# def flask_server():
#     """Start Flask server via command line"""
#     # Set environment variables
#     env = os.environ.copy()
#     env["FLASK_APP"] = "main.py"
#     env["DYNAMODB_TABLE"] = "chat_app_jrw_test"
    
#     # Get the backend directory path
#     backend_dir = Path(__file__).parent.parent
    
#     # Use the Python interpreter from the current virtual environment
#     python_executable = sys.executable
    
#     print("\n=== Starting Flask server ===")
#     print(f"Using Python from: {python_executable}")
    
#     # Start Flask server
#     process = subprocess.Popen(
#         [python_executable, "-m", "flask", "run", "--port", "5001"],
#         env=env,
#         cwd=str(backend_dir),
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#         bufsize=1,
#         universal_newlines=True
#     )
    
#     # Function to check if server is up
#     def is_server_up():
#         try:
#             response = requests.get("http://localhost:5001/health")
#             return response.status_code == 200
#         except:
#             return False
    
#     # Wait for server to start
#     timeout = time.time() + 30  # 30 second timeout
#     while not is_server_up():
#         if time.time() > timeout:
#             stdout, stderr = process.communicate()
#             print("\n=== Flask server failed to start ===")
#             print("=== STDOUT ===")
#             print(stdout)
#             print("\n=== STDERR ===")
#             print(stderr)
#             process.kill()
#             raise RuntimeError("Flask server failed to start")
#         time.sleep(0.5)
        
#         # Check if process has terminated
#         if process.poll() is not None:
#             stdout, stderr = process.communicate()
#             print("\n=== Flask server terminated unexpectedly ===")
#             print("=== STDOUT ===")
#             print(stdout)
#             print("\n=== STDERR ===")
#             print(stderr)
#             raise RuntimeError("Flask server terminated unexpectedly")
    
#     print("Flask server started successfully")
    
#     yield
    
#     # Kill the server after tests
#     process.kill()
#     stdout, stderr = process.communicate()
#     if stdout:
#         print("\n=== Flask server STDOUT ===")
#         print(stdout)
#     if stderr:
#         print("\n=== Flask server STDERR ===")
#         print(stderr)

@pytest.fixture(scope="session")
def test_db():
    """Test database fixture"""
    db = DynamoDB(table_name='chat_app_jrw_test')
    
    # Print and clear existing items
    print("\n=== Current items in test database ===")
    response = db.table.scan()
    items = response['Items']
    for item in items:
        print(f"- {item}")
    
    print("\n=== Clearing test database (preserving general channel) ===")
    with db.table.batch_writer() as batch:
        for item in items:
            # Skip the general channel metadata
            if item['PK'] == 'CHANNEL#general' and item['SK'] == '#METADATA':
                continue
            batch.delete_item(
                Key={
                    'PK': item['PK'],
                    'SK': item['SK']
                }
            )
    print("Test database cleared (general channel preserved)")
    
    return db

@pytest.fixture(scope="function")
def driver():
    """Selenium WebDriver fixture using Firefox"""
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--no-sandbox")
    firefox_options.add_argument("--disable-dev-shm-usage")
    firefox_options.log.level = "fatal"  # Only show fatal errors
    
    try:
        driver = webdriver.Firefox(options=firefox_options)
        print("Firefox driver created successfully")
        yield driver
    except Exception as e:
        print(f"\nError creating Firefox driver: {str(e)}")
        raise
    finally:
        if 'driver' in locals():
            driver.quit()

@pytest.fixture(scope="function")
def second_driver():
    """Second Selenium WebDriver fixture using Chrome"""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Suppress unnecessary logs
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")
    
    driver = webdriver.Chrome(options=chrome_options)
    yield driver
    driver.quit() 