from app import create_app
from app.db.ddb import DynamoDB
import logging
from app.services.user_service import UserService

logging.basicConfig(level=logging.INFO)

app = create_app()
db = DynamoDB()

print("\n=== DynamoDB Configuration ===")
print(f"Table name: {db.table.name}")
print("============================\n")

# Initialize UserService
user_service = UserService(db.table.name)

# Create bot user on startup
try:
    user_service.create_bot_user(email='bot@example.com', name='Bot')
    print("Bot user created or already exists.")
except Exception as e:
    print(f"Error creating bot user: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True) 