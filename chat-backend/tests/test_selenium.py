from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pytest
import requests
import threading

TEST_USER_1 = {"name": "Test User One", "email": "test1@example.com", "password": "password123"}
TEST_USER_2 = {"name": "Test User Two", "email": "test2@example.com", "password": "password123"}

def login_user(driver, email, password):
    """Login a user and wait for redirect to chat page"""
    print(f"\n=== Logging in user {email} ===")
    
    # Navigate to auth page
    driver.get("http://localhost:5174/auth")
    time.sleep(2)
    
    # Fill in login form
    driver.find_element(By.ID, "login-email").send_keys(email)
    driver.find_element(By.ID, "login-password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    # Wait for redirect to chat page
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Chat App')]"))
    )
    print(f"User {email} logged in and redirected to chat")
    time.sleep(5)  # Give it a moment to establish connection and load channels

def register_user(driver, name, email, password="password123"):
    """Register a new user and wait for redirect to chat page"""
    print(f"\n=== Registering user {name} ===")
    
    # Navigate to auth page
    driver.get("http://localhost:5174/auth")
    time.sleep(2)
    
    # Click register button
    register_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Need an account? Register')]"))
    )
    register_button.click()
    
    # Fill in registration form
    driver.find_element(By.ID, "name").send_keys(name)
    driver.find_element(By.ID, "email").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    # Wait for redirect to chat page
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Chat App')]"))
    )
    print(f"User {name} registered and redirected to chat")
    time.sleep(5)  # Give it a moment to establish connection and load channels

@pytest.fixture(scope="function")
def test_users(driver, test_db):
    """Create test users at the start of each test using registration API"""
    print("\n=== Setting up test users ===")
    
    # Register both test users through API
    for user in [TEST_USER_1, TEST_USER_2]:
        try:
            response = requests.post(
                "http://localhost:5001/auth/register",
                json={
                    "name": user["name"],
                    "email": user["email"],
                    "password": user["password"]
                }
            )
            response.raise_for_status()
            print(f"Created test user: {user['name']}")
        except Exception as e:
            print(f"Error creating user {user['name']}: {e}")
            raise
    
    yield TEST_USER_1, TEST_USER_2

def test_user_registration(driver, test_db):
    """Test user registration through the frontend"""
    print("\n=== Starting user registration test ===")
    
    register_user(driver, "Test User", "testanother@example.com")
    
    # Verify we can see general channel in UI
    print("\n=== Verifying chat page content ===")
    try:
        # Wait for general channel to appear
        element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '#general')]"))
        )
        print(f"Found general channel: '{element.text}'")
            
    except Exception as e:
        print("\nTimeout waiting for general channel in UI!")
        print("=== Current page text ===")
        print(driver.find_element(By.TAG_NAME, "body").text)
        raise AssertionError("General channel not found in UI") from e

def test_two_users_chat(driver, second_driver, test_db):
    """Test chat functionality between two users"""
    print("\n=== Starting two users chat test ===")
    
    # Register both users
    register_user(driver, "User One", "user1test@example.com")
    register_user(second_driver, "User Two", "user2@example.com")
    
    print("\n=== Checking for general channel in second user's UI ===")
    try:
        general_channel = WebDriverWait(second_driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '#general')]"))
        )
        print("Found general channel:", general_channel.text)
    except Exception as e:
        print("Could not find general channel in second user's UI!")
        print("Current page text:")
        print(second_driver.find_element(By.TAG_NAME, "body").text)
        raise
    
    # Continue with chat test...
    print("\n=== Starting chat test ===")
    # First user sends a message in general channel
    message_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='message-input']"))
    )
    message_input.send_keys("Hello from User One!")
    # Find and click the send button using data-testid
    send_button = driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']")
    send_button.click()
    
    # Wait for message to appear in second user's window
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hello from User One!')]"))
    )
    
    # Second user sends a reply
    message_input = second_driver.find_element(By.CSS_SELECTOR, "[data-testid='message-input']")
    message_input.send_keys("Hi User One, from User Two!")
    second_driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']").click()
    
    # Wait for reply to appear in first user's window
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hi User One, from User Two!')]"))
    )
    
    print("\n=== Chat test completed successfully ===")

def test_channel_creation_and_join(driver, second_driver, test_db, test_users):
    """Test creating a new channel and having another user join it"""
    print("\n=== Starting channel creation and join test ===")
    
    test_user_1, test_user_2 = test_users
    
    # Login both users
    login_user(driver, test_user_1["email"], test_user_1["password"])
    login_user(second_driver, test_user_2["email"], test_user_2["password"])
    
    # First user creates a new channel
    print("\n=== Creating new channel ===")
    create_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='create-channel-button']"))
    )
    create_button.click()
    
    # Fill in channel name
    channel_name = "newchan"
    channel_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Channel name']"))
    )
    channel_input.send_keys(channel_name)
    driver.find_element(By.XPATH, "//button[contains(text(), 'Create')]").click()
    
    # Wait for channel to appear in second user's available channels
    print("\n=== Waiting for channel to appear for second user ===")
    channel_element = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-testid='channel-{channel_name}']"))
    )
    
    # Second user joins the channel
    print("\n=== Second user joining channel ===")
    channel_element = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-testid='channel-{channel_name}']"))
    )
    
    # Find join button using channel-specific ID
    join_button = channel_element.find_element(By.CSS_SELECTOR, f"[data-testid^='join-channel-button-']")
    join_button.click()
    
    # Test message exchange in new channel
    print("\n=== Testing message exchange in new channel ===")
    # First user sends a message
    message_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='message-input']"))
    )
    message_input.send_keys("Hello in the new channel!")
    send_button = driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']")
    send_button.click()
    
    # Wait for message to appear in second user's window
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hello in the new channel!')]"))
    )
    
    # Second user sends a reply
    message_input = second_driver.find_element(By.CSS_SELECTOR, "[data-testid='message-input']")
    message_input.send_keys("Hi! I joined your new channel!")
    second_driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']").click()
    
    # Wait for reply to appear in first user's window
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hi! I joined your new channel!')]"))
    )
    
    print("\n=== Channel creation and join test completed successfully ===")

def test_direct_messages(driver, second_driver, test_db, test_users):
    """Test direct messaging between two users"""
    print("\n=== Starting direct messages test ===")
    
    # Create threads for parallel login
    login1 = threading.Thread(target=login_user, args=(driver, TEST_USER_1["email"], TEST_USER_1["password"]))
    login2 = threading.Thread(target=login_user, args=(second_driver, TEST_USER_2["email"], TEST_USER_2["password"]))
    
    # Start both logins
    login1.start()
    login2.start()
    
    # Wait for both logins to complete
    login1.join()
    login2.join()
    
    # First user starts a DM
    print("\n=== Creating new DM ===")
    
    # Click new DM button
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='new-dm-button']"))
    ).click()
    
    # Wait for user selector popup and select second user
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, f"[data-testid='user-select-{TEST_USER_2['name']}']"))
    ).click()
    
    # Wait for DM channel to be created and appear in sidebar
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, f"//span[text()='{TEST_USER_2['name']}']"))
    )
    
    # Wait for message input to show we're messaging the correct user
    message_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"input[placeholder='Message {TEST_USER_2['name']}']"))
    )
    
    # Send a message in the DM
    message_input.send_keys("Hello in DM!")
    driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']").click()
    
    # Wait for DM channel to appear in second user's sidebar and click it
    dm_channel = WebDriverWait(second_driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, f"//span[text()='{TEST_USER_1['name']}']"))
    )
    dm_channel.click()
    
    # Wait for message to appear in second user's window
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, f"//span[text()='{TEST_USER_1['name']}']"))
    )
    
    # Verify message content
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//p[text()='Hello in DM!']"))
    )
    
    # Second user sends a reply
    message_input = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='message-input']"))
    )
    message_input.send_keys("Hi back in DM!")
    second_driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']").click()
    
    # Wait for reply in first user's window
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, f"//span[text()='{TEST_USER_2['name']}']"))
    )
    
    # Verify reply content
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//p[text()='Hi back in DM!']"))
    )
    
    # Test reactions
    print("\n=== Testing message reactions ===")
    
    # First user adds a reaction to second user's message
    add_reaction_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid^='add-reaction-']"))
    )
    add_reaction_button.click()
    
    # Wait for emoji picker to be visible first
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='emoji-picker-']"))
    )
    
    # Use JavaScript to click the thumbs up emoji
    driver.execute_script("""
        const picker = document.querySelector('em-emoji-picker');
        const thumbsUp = picker.shadowRoot.querySelector('button[aria-label="👍"]');
        thumbsUp.click();
    """)
    
    # Wait for reaction to appear
    reaction = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='reaction-👍-']"))
    )
    
    # Second user adds the same reaction
    add_reaction_button = WebDriverWait(second_driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid^='add-reaction-']"))
    )
    add_reaction_button.click()
    
    # Wait for emoji picker and use JavaScript to click thumbs up
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='emoji-picker-']"))
    )
    second_driver.execute_script("""
        const picker = document.querySelector('em-emoji-picker');
        const thumbsUp = picker.shadowRoot.querySelector('button[aria-label="👍"]');
        thumbsUp.click();
    """)
    
    # Wait for reaction count to update to 2 for second user
    print("Waiting for second user to see reaction count = 2")
    reaction_button = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='reaction-👍-']"))
    )
    WebDriverWait(second_driver, 10).until(
        lambda d: "2" in d.find_element(By.CSS_SELECTOR, "[data-testid^='reaction-👍-']").text
    )
    
    # Wait for reaction count to update to 2 for first user
    print("Waiting for first user to see reaction count = 2")
    reaction_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='reaction-👍-']"))
    )
    WebDriverWait(driver, 10).until(
        lambda d: "2" in d.find_element(By.CSS_SELECTOR, "[data-testid^='reaction-👍-']").text
    )
    
    print("\n=== Direct messages test completed successfully ===")

        
