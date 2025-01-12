from app import create_app, get_socketio
import os

app = create_app()
socketio = get_socketio()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=True, port=port) 