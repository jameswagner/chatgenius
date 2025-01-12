from app import create_app, get_socketio
import os
import argparse

# Set up argument parsing
parser = argparse.ArgumentParser(description='Run the chat server')
parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')

app = create_app()
socketio = get_socketio()

# This enables Flask CLI integration with SocketIO
cli = app.cli

if __name__ == '__main__':
    args = parser.parse_args()
    socketio.run(app, debug=True, port=args.port) 