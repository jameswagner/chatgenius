from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def test_user_registration(driver, app, test_db):
    """Test user registration through the frontend"""
    # Navigate to auth page
    driver.get("http://localhost:5174/auth")
    time.sleep(2)  # Give the page a moment to load
    

    # Wait for and click the "Register" link to switch to registration form
    print("\n=== Trying to find Register button ===")
    try:
        register_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Need an account? Register')]"))
        )
        print(f"Found register button: '{register_button.text}', visible: {register_button.is_displayed()}")
        register_button.click()
        print("Clicked register button")
    except Exception as e:
        raise
    
    # Now wait for registration form fields
    print("\n=== Waiting for name field ===")
    try:
        name_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "name"))
        )
        print(f"Found name field: visible: {name_field.is_displayed()}")
    except Exception as e:

        raise
    
    # Fill in registration form
    driver.find_element(By.ID, "name").send_keys("Test User")
    driver.find_element(By.ID, "email").send_keys("testanother@example.com")
    driver.find_element(By.ID, "password").send_keys("password123")
    
    print("\n=== Looking for submit button ===")
    submit_buttons = driver.find_elements(By.XPATH, "//button[@type='submit']")
    print(f"Found {len(submit_buttons)} submit buttons:")
    for button in submit_buttons:
        print(f"Button text: '{button.text}', visible: {button.is_displayed()}")
    
    # Click submit button
    submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
    print(f"\nClicking submit button: '{submit_button.text}'")
    submit_button.click()
    
    # Wait for redirect to chat page after successful registration
    print("\n=== Waiting for redirect ===")
    try:
        WebDriverWait(driver, 10).until(
            EC.url_to_be("http://localhost:5174/chat")
        )
        print(f"Current URL after redirect: {driver.current_url}")
    except Exception as e:
        print(f"Error during redirect: {str(e)}")
        print("\n=== Page Content After Error ===")
        print(driver.page_source)
        raise
    
    # Verify user was created in database
    user = test_db.get_user_by_email("test@example.com")
    assert user is not None
    assert user.name == "Test User"
    
    # Verify we're on the chat page
    #print("\n=== Final Page Content ===")
    #print(driver.page_source)
    assert "general" in driver.page_source.lower()  # General channel should be visible 

def test_two_users_chat(driver, second_driver, app, test_db):
    """Test chat functionality between two users"""
    # Register first user
    driver.get("http://localhost:5174/auth")
    time.sleep(3)
    
    # Click register button for first user
    register_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Need an account? Register')]"))
    )
    register_button.click()
    
    # Fill in registration for first user
    driver.find_element(By.ID, "name").send_keys("User One")
    driver.find_element(By.ID, "email").send_keys("user1test@example.com")
    driver.find_element(By.ID, "password").send_keys("password123")
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    # Wait for redirect to chat page
    WebDriverWait(driver, 10).until(
        EC.url_to_be("http://localhost:5174/chat")
    )
    
    # Register second user in different window
    second_driver.get("http://localhost:5174/auth")
    time.sleep(2)
    
    # Click register button for second user
    register_button = WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Need an account? Register')]"))
    )
    register_button.click()
    
    # Fill in registration for second user
    second_driver.find_element(By.ID, "name").send_keys("User Two")
    second_driver.find_element(By.ID, "email").send_keys("user2@example.com")
    second_driver.find_element(By.ID, "password").send_keys("password123")
    second_driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    # Wait for redirect to chat page
    WebDriverWait(second_driver, 10).until(
        EC.url_to_be("http://localhost:5174/chat")
    )
    
    # First user sends a message in general channel
    message_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
    )
    message_input.send_keys("Hello from User One!")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    
    # Wait for message to appear in second user's window
    WebDriverWait(second_driver, 10).until(
        EC.presence_of_element_located((By.xpath, "//*[contains(text(), 'Hello from User One!')]"))
    )
    
    # Second user sends a reply
    message_input = second_driver.find_element(By.CSS_SELECTOR, "input[type='text']")
    message_input.send_keys("Hi User One, from User Two!")
    second_driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    
    # Wait for reply to appear in first user's window
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.xpath, "//*[contains(text(), 'Hi User One, from User Two!')]"))
    )
    
    # Verify messages are in the database
    messages = test_db.get_channel_messages("general")
    assert len(messages) == 2
    assert any(m.content == "Hello from User One!" for m in messages)
    assert any(m.content == "Hi User One, from User Two!" for m in messages) 