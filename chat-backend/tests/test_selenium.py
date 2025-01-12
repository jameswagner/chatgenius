from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def register_user(driver, name, email):
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
    driver.find_element(By.ID, "password").send_keys("password123")
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    # Wait for redirect to chat page
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Chat App')]"))
    )
    print(f"User {name} registered and redirected to chat")
    time.sleep(5)  # Give it a moment to establish connection and load channels

def test_user_registration(driver):
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

def test_two_users_chat(driver, second_driver):
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
    # Find and click the send button (SVG)
    send_button = driver.find_element(By.XPATH, "//button[.//svg[contains(@class, 'h-5')]]")
    send_button.click()
    
    # Wait for message to appear in second user's window
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hello from User One!')]"))
    )
    
    # Second user sends a reply
    message_input = second_driver.find_element(By.CSS_SELECTOR, "[data-testid='message-input']")
    message_input.send_keys("Hi User One, from User Two!")
    second_driver.find_element(By.XPATH, "//button[.//svg[contains(@class, 'h-5')]]").click()
    
    # Wait for reply to appear in first user's window
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Hi User One, from User Two!')]"))
    )
    
    print("\n=== Chat test completed successfully ===")

        
