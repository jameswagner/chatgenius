from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pytest
import requests
import threading
from selenium.webdriver.common.keys import Keys

TEST_USER_1 = {"name": "Test User One", "email": "test1@example.com", "password": "password123"}
TEST_USER_2 = {"name": "Test User Two", "email": "test2@example.com", "password": "password123"}

# Utility Functions
def send_and_verify_message(sender_driver, receiver_driver, message, is_dm=False, sender_name=None):
    """Helper to send a message and verify it appears for the receiver"""
    message_input = WebDriverWait(sender_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='message-input']"))
    )
    message_input.send_keys(message)
    sender_driver.find_element(By.CSS_SELECTOR, "[data-testid='send-message-button']").click()
    
    if is_dm and sender_name:
        # For DMs, receiver needs to click the channel first
        dm_channel = WebDriverWait(receiver_driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//span[text()='{sender_name}']"))
        )
        dm_channel.click()
    
    WebDriverWait(receiver_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{message}')]"))
    )

def setup_two_users(driver1, driver2, use_registration=False):
    """Set up two users either via registration or login"""
    if use_registration:
        register_user(driver1, "User One", "user1test@example.com")
        register_user(driver2, "User Two", "user2@example.com")
    else:
        # Parallel login
        login1 = threading.Thread(target=login_user, args=(driver1, TEST_USER_1["email"], TEST_USER_1["password"]))
        login2 = threading.Thread(target=login_user, args=(driver2, TEST_USER_2["email"], TEST_USER_2["password"]))
        login1.start()
        login2.start()
        login1.join()
        login2.join()

def verify_general_channel(driver):
    """Verify general channel is visible"""
    try:
        element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '#general')]"))
        )
        print(f"Found general channel: '{element.text}'")
        return element
    except Exception as e:
        print("\nTimeout waiting for general channel in UI!")
        print("=== Current page text ===")
        print(driver.find_element(By.TAG_NAME, "body").text)
        raise AssertionError("General channel not found in UI") from e

def login_user(driver, email, password):
    """Login a user and wait for redirect to chat page"""
    print(f"\n=== Logging in user {email} ===")
    
    driver.get("http://localhost:5174/auth")
    time.sleep(2)
    
    driver.find_element(By.ID, "login-email").send_keys(email)
    driver.find_element(By.ID, "login-password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Chat App')]"))
    )
    print(f"User {email} logged in and redirected to chat")
    time.sleep(5)

def register_user(driver, name, email, password="password123"):
    """Register a new user and wait for redirect to chat page"""
    print(f"\n=== Registering user {name} ===")
    
    driver.get("http://localhost:5174/auth")
    time.sleep(2)
    
    register_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Need an account? Register')]"))
    )
    register_button.click()
    
    driver.find_element(By.ID, "name").send_keys(name)
    driver.find_element(By.ID, "email").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Chat App')]"))
    )
    print(f"User {name} registered and redirected to chat")
    time.sleep(5)

@pytest.fixture(scope="function")
def test_users(driver, test_db):
    """Create test users at the start of each test using registration API"""
    print("\n=== Setting up test users ===")
    
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
    verify_general_channel(driver)

def test_two_users_chat(driver, second_driver, test_db):
    """Test chat functionality between two users"""
    print("\n=== Starting two users chat test ===")
    
    setup_two_users(driver, second_driver, use_registration=True)
    verify_general_channel(second_driver)
    
    # Test message exchange
    send_and_verify_message(driver, second_driver, "Hello from User One!")
    send_and_verify_message(second_driver, driver, "Hi User One, from User Two!")

def test_channel_creation_and_join(driver, second_driver, test_db, test_users):
    """Test creating a new channel and having another user join it"""
    print("\n=== Starting channel creation and join test ===")
    
    test_user_1, test_user_2 = test_users
    setup_two_users(driver, second_driver)
    
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
    
    # Wait for channel to appear for second user and join
    print("\n=== Second user joining channel ===")
    channel_element = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-testid='channel-{channel_name}']"))
    )
    join_button = channel_element.find_element(By.CSS_SELECTOR, f"[data-testid^='join-channel-button-']")
    join_button.click()
    
    # Test message exchange in new channel
    send_and_verify_message(driver, second_driver, "Hello in the new channel!")
    send_and_verify_message(second_driver, driver, "Hi! I joined your new channel!")

def test_direct_messages(driver, second_driver, test_db, test_users):
    """Test direct messaging between two users"""
    print("\n=== Starting direct messages test ===")
    
    setup_two_users(driver, second_driver)
    
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
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"input[placeholder='Message {TEST_USER_2['name']}']"))
    )
    
    # Test message exchange
    send_and_verify_message(driver, second_driver, "Hello in DM!", is_dm=True, sender_name=TEST_USER_1['name'])
    send_and_verify_message(second_driver, driver, "Hi back in DM!", is_dm=False)  # No need to click again for second message
    
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

def test_thread_replies(driver, second_driver, test_db, test_users):
    """Test replying in threads and adding reactions to replies"""
    print("\n=== Starting thread replies test ===")
    
    setup_two_users(driver, second_driver)
    
    # First user sends a message in general channel
    message_text = "Main message for thread testing"
    send_and_verify_message(driver, second_driver, message_text)
    
    # Wait for the message to be visible and find its container
    message_element = WebDriverWait(second_driver, 30).until(
        EC.presence_of_element_located((By.XPATH, f"//p[contains(text(), '{message_text}')]"))
    )
    
    # Debug - Print the HTML structure
    print("\nDebug - Message element HTML:")
    print(message_element.get_attribute('outerHTML'))
    print("\nDebug - Parent element HTML:")
    parent = message_element.find_element(By.XPATH, "..")
    print(parent.get_attribute('outerHTML'))
    print("\nDebug - Grandparent element HTML:")
    grandparent = parent.find_element(By.XPATH, "..")
    print(grandparent.get_attribute('outerHTML'))

    # Find the message container and get its ID
    message_container = message_element.find_element(By.XPATH, "ancestor::div[contains(@class, 'flex items-start p-2')]")
    message_id = message_container.get_attribute("id")
    print(f"\nDebug - Message container HTML:")
    print(message_container.get_attribute('outerHTML'))
    print(f"\nDebug - Message container ID: {message_id}")
    
    if message_id:
        message_id = message_id.replace("message-", "")
        print(f"Debug - Looking for button with data-testid: reply-in-thread-button-{message_id}")

        # Find the reply button directly by its data-testid
        reply_button = WebDriverWait(second_driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"button[data-testid='reply-in-thread-button-{message_id}']"))
        )
        print("Debug - Reply button found successfully")
        reply_button.click()
    else:
        print("Debug - No message ID found in container")
    
    # Send reply in thread
    reply_input = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='thread-reply-input']"))
    )
    reply_input.send_keys("This is a thread reply!")
    reply_input.send_keys(Keys.RETURN)
    
    # Verify reply appears for both users
    for driver in [driver, second_driver]:
        # Verify reply count shows "1 reply"
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), '1 reply')]"))
        )
        
        # Click to show replies if needed
        show_replies = driver.find_element(By.CSS_SELECTOR, f"[data-testid='show-replies-button-{message_id}']")
        show_replies.click()
        
        # Verify reply content
        reply_text = "This is a thread reply!"
        print(f"\nDebug - Looking for reply with text: {reply_text}")
        reply = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//p[contains(text(), '{reply_text}')]"))
        )
        print("Debug - Found reply message")
        print("Debug - Reply HTML:")
        print(reply.get_attribute('outerHTML'))

        # Get the reply container by finding the closest message container div
        reply_container = reply.find_element(By.XPATH, "ancestor::div[@id[starts-with(., 'message-')]]")
        print("\nDebug - Reply container HTML:")
        print(reply_container.get_attribute('outerHTML'))

        reply_id = reply_container.get_attribute("id").replace("message-", "")
        print(f"\nDebug - Reply ID: {reply_id}")

        # Find and click the add reaction button for the reply
        add_reaction_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f"[data-testid='add-reaction-{reply_id}']"))
        )
        add_reaction_button.click()
    
    # First user adds reaction to the reply
    print("\nDebug - First user adding reaction")
    print("Debug - Looking for add reaction button")
    add_reaction_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"[data-testid='add-reaction-{reply_id}']"))
    )
    print("Debug - Found add reaction button")
    print("Debug - Add reaction button HTML:")
    print(add_reaction_button.get_attribute('outerHTML'))
    add_reaction_button.click()
    
    # Wait for emoji picker and add reaction
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='emoji-picker-']"))
    )
    driver.execute_script("""
        const picker = document.querySelector('em-emoji-picker');
        const thumbsUp = picker.shadowRoot.querySelector('button[aria-label="👍"]');
        thumbsUp.click();
    """)
    
    # Second user adds the same reaction to the reply
    reply = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='thread-reply']"))
    )
    add_reaction_button = reply.find_element(By.CSS_SELECTOR, "[data-testid^='add-reaction-']")
    add_reaction_button.click()
    
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid^='emoji-picker-']"))
    )
    second_driver.execute_script("""
        const picker = document.querySelector('em-emoji-picker');
        const thumbsUp = picker.shadowRoot.querySelector('button[aria-label="👍"]');
        thumbsUp.click();
    """)
    
    # Verify reaction count for both users
    for d in [driver, second_driver]:
        reply = WebDriverWait(d, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='thread-reply']"))
        )
        reaction = reply.find_element(By.CSS_SELECTOR, "[data-testid^='reaction-👍-']")
        WebDriverWait(d, 10).until(
            lambda x: "2" in reaction.text
        )
    
    print("\n=== Thread replies test completed successfully ===")

        
