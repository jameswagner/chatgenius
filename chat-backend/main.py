from app import create_app
from app.db.ddb import DynamoDB
import logging

logging.basicConfig(level=logging.INFO)

app = create_app()
db = DynamoDB()

print("\n=== DynamoDB Configuration ===")
print(f"Table name: {db.table.name}")
print("============================\n")

if __name__ == '__main__':
    app.run(debug=True) 