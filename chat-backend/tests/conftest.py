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
from tests.utils import create_chat_table

# @pytest.fixture(scope="session", autouse=True)
# def flask_server():
#     """Start Flask server"""
#     backend_dir = Path(__file__).parent.parent
    
#     # Start Flask server
#     flask_process = start_flask_server(backend_dir)
#     print("Started Flask server, checking health...")
    
#     if not wait_for_flask():
#         print("\n=== Flask server failed to start ===")
#         stdout, stderr = flask_process.communicate()
#         print("\n=== Flask STDOUT ===")
#         print(stdout)
#         print("\n=== Flask STDERR ===")
#         print(stderr)
#         flask_process.kill()
#         raise RuntimeError("Flask server failed to start")
    
#     print("Flask server is healthy")
#     yield
    
#     # Kill Flask server after tests
#     flask_process.kill()
#     stdout, stderr = flask_process.communicate()
#     if stdout:
#         print("\n=== Flask server STDOUT ===")
#         print(stdout)
#     if stderr:
#         print("\n=== Flask server STDERR ===")
#         print(stderr)

# @pytest.fixture(scope="session", autouse=True)
# def frontend_server():
#     """Start the frontend development server"""
#     print("\nStarting frontend development server...")
    
#     # Install dependencies and cross-env
#     install_process = subprocess.run(
#         ["C:\\Program Files\\nodejs\\npm.cmd", "install"],
#         cwd="chat-frontend",
#         capture_output=True,
#         text=True
#     )
#     if install_process.returncode != 0:
#         print("\n=== Failed to install frontend dependencies ===")
#         print(install_process.stdout)
#         print(install_process.stderr)
#         raise RuntimeError("Failed to install frontend dependencies")

#     # Install cross-env explicitly
#     cross_env_process = subprocess.run(
#         ["C:\\Program Files\\nodejs\\npm.cmd", "install", "--save-dev", "cross-env"],
#         cwd="chat-frontend",
#         capture_output=True,
#         text=True
#     )
#     if cross_env_process.returncode != 0:
#         print("\n=== Failed to install cross-env ===")
#         print(cross_env_process.stdout)
#         print(cross_env_process.stderr)
#         raise RuntimeError("Failed to install cross-env")
    
#     # Start frontend server from chat-frontend directory
#     process = subprocess.Popen(
#         ["C:\\Program Files\\nodejs\\npm.cmd", "run", "dev:test"],
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         cwd="chat-frontend",
#         text=True,
#         env={"PATH": os.environ["PATH"] + os.pathsep + os.path.join(os.getcwd(), "chat-frontend", "node_modules", ".bin")}
#     )

#     try:
#         wait_for_frontend(process)
#         yield process
#     finally:
#         print("\nShutting down frontend server...")
#         process.terminate()
#         process.wait()

# def start_flask_server(backend_dir):
#     """Start Flask server with test database"""
#     env = os.environ.copy()
#     env["FLASK_APP"] = "main.py"
#     env["DYNAMODB_TABLE"] = "chat_app_jrw_test"
    
#     python_executable = sys.executable
#     print("\n=== Starting Flask server ===")
#     print(f"Using Python from: {python_executable}")
    
#     return subprocess.Popen(
#         [python_executable, "main.py", "--port", "5001"],
#         env=env,
#         cwd=str(backend_dir),
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#         bufsize=1,
#         universal_newlines=True
#     )

# def start_frontend_server(frontend_dir):
#     """Start frontend dev server"""
#     print("\n=== Starting frontend dev server ===")
#     return subprocess.Popen(
#         ["C:\\Program Files\\nodejs\\npm.cmd", "run", "dev:test"],
#         cwd=str(frontend_dir),
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         text=True,
#         bufsize=1,
#         universal_newlines=True
#     )

# def wait_for_flask(timeout=30):
#     """Wait for Flask server to be healthy"""
#     end_time = time.time() + timeout
#     while time.time() < end_time:
#         try:
#             response = requests.get("http://localhost:5001/health")
#             if response.status_code == 200:
#                 return True
#         except:
#             pass
#         time.sleep(0.5)
#     return False

# def wait_for_frontend(process, timeout=30):
#     """Wait for frontend server to be ready"""
#     start_time = time.time()
#     while time.time() - start_time < timeout:
#         # Print any new output
#         while True:
#             line = process.stdout.readline()
#             if not line and process.poll() is not None:
#                 print("\n=== Frontend server failed to start ===")
#                 stdout, stderr = process.communicate()
#                 print("\n=== Frontend STDOUT ===")
#                 print(stdout)
#                 print("\n=== Frontend STDERR ===")
#                 print(stderr)
#                 return False
#             if not line:
#                 break
#             print(f"Frontend: {line.strip()}")
            
#         # First check Vite server health
#         try:
#             vite_response = requests.get("http://localhost:5174/health")
#             if vite_response.status_code == 200:
#                 print("Vite server is healthy")
#             else:
#                 print("Vite server is not healthy will try again")
#         except requests.exceptions.ConnectionError:
#             pass
            
#         # Check if process died
#         if process.poll() is not None:
#             print("\n=== Frontend server failed to start ===")
#             stdout, stderr = process.communicate()
#             print("\n=== Frontend STDOUT ===")
#             print(stdout)
#             print("\n=== Frontend STDERR ===")
#             print(stderr)
#             return False
            
#         time.sleep(0.1)
    
#     print("Frontend server failed to start within 30 seconds")
#     return False

@pytest.fixture(scope="function")
def test_db():
    """Test database fixture"""
    table_name = 'chat_app_jrw_test'
    table = create_chat_table(table_name)
    db = DynamoDB(table_name=table_name)
    
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