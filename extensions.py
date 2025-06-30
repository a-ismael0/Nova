from flask_socketio import SocketIO

# Initialize SocketIO instance
socketio = SocketIO(
    ping_timeout=60,
    ping_interval=25,
    cors_allowed_origins="*",
    engineio_logger=True,
    logger=True,
    async_mode='threading'
)