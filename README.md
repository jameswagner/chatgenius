# Real-Time Chat Application

A full-stack real-time chat application inspired by Slack, built with React, TypeScript, Python Flask, SQLite, and WebSocket communication.

## Project Structure

### Backend (`/chat-backend`)

The backend is built with Python Flask and uses SQLite for data persistence. Key components:

- `app.py` - Main Flask application with route handlers
- `app/`
  - `auth/` - Authentication service and middleware
  - `db/` - SQLite database implementation
  - `models/` - Data models (User, Channel, Message, etc.)
  - `storage/` - Local file storage implementation
  
Key technologies:
- Flask for REST API
- Flask-SocketIO for real-time communication
- SQLite for data storage
- JWT for authentication

### Frontend (`/chat-frontend`)

The frontend is built with React and TypeScript. Key components:

- `src/`
  - `components/` - Reusable UI components
    - `Chat/` - Chat-related components (ChatLayout, MessageList, etc.)
    - `Layout/` - Common layout components
    - `Auth/` - Authentication forms
  - `services/` - API and WebSocket services
  - `types/` - TypeScript type definitions
  - `utils/` - Utility functions
  - `pages/` - Page components

Key technologies:
- React
- TypeScript
- TailwindCSS for styling
- Axios for HTTP requests
- Socket.IO client for real-time communication

### Infrastructure (`/slack-clone`)

Contains AWS CDK code for future cloud deployment (not currently in use).

## Features

- Real-time messaging with WebSocket support
- User authentication (register/login)
- Channel management (create, join, leave)
- Direct messaging between users
- Thread replies to messages
- Message reactions (emojis)
- File attachments
- User presence (online/away/busy/offline)
- Message persistence
- Real-time status updates

## Running Locally

### Backend Setup

cd chat-backend
python -m venv venv
source venv/bin/activate # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py


### Frontend Setup

cd chat-frontend
npm install
npm run dev


The application will be available at `http://localhost:5173`

## Known Issues

1. Message timestamps are displayed in UTC instead of user's local timezone
2. Uploaded files do not render properly in the UI
3. WebSocket reconnection handling needs improvement
4. No message delivery confirmation
5. Limited error handling for network issues

## Next Steps

1. Message search functionality
   - Implement full-text search
   - Add search filters (by user, channel, date)

2. File handling improvements
   - Migrate file storage to AWS S3
   - Fix file preview and download in chat
   - Add progress indicators for uploads
   - Implement file type validation

3. AWS Deployment
   - Deploy using AWS CDK
   - Migrate to AWS services:
     - Cognito for authentication
     - DynamoDB for data storage
     - S3 for file storage
     - ElastiCache for real-time features
     - API Gateway and Lambda for API
     - CloudFront for static content delivery

4. Additional Features
   - Message editing and deletion
   - Rich text formatting
   - User profiles
   - Channel archiving
   - Message pinning
   - User groups and permissions
   - Message scheduling
   - Voice and video calls

5. Performance Improvements
   - Message pagination
   - Lazy loading of content
   - Image optimization
   - Caching strategies

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.