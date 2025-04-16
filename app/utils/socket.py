import logging
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

class SocketManager:
    def __init__(self, host='localhost', port=8080, socketio=None):
        self.host = host
        self.port = port
        self.socketio = socketio
        logger.info(f"SocketManager initialized with host={host}, port={port}")
        if socketio:
            logger.info("SocketIO instance provided during initialization")

    def initialize_socketio(self, app):
        """Initialize Flask-SocketIO with the Flask app."""
        if not self.socketio:
            self.socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
            logger.info("Flask-SocketIO initialized with threading mode")
        return self.socketio

    def send_message(self, message):
        """Send a message to all connected clients."""
        try:
            if self.socketio:
                # Parse the JSON message to extract event and data
                import json
                msg_data = json.loads(message)
                event_name = msg_data.get('event', 'message')
                event_data = msg_data.get('data', {})
                
                # Emit the event to all clients
                self.socketio.emit(event_name, event_data)
                logger.debug(f"Emitted {event_name} event: {str(event_data)[:100]}...")
            else:
                logger.warning("Cannot send message: SocketIO not initialized")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            print(f"Error sending message: {e}")

    def close_connection(self):
        """This method is kept for compatibility but is no longer needed."""
        logger.info("close_connection() is not needed with Flask-SocketIO")
        pass

# Helper functions for direct socketio usage
def emit_event(socketio, event_name, data):
    """Emit an event using socketio with error handling."""
    try:
        if socketio:
            socketio.emit(event_name, data)
            logger.debug(f"Emitted {event_name} event: {str(data)[:100]}...")
            return True
        else:
            logger.warning(f"Cannot emit {event_name}: SocketIO not available")
            return False
    except Exception as e:
        logger.error(f"Error emitting {event_name}: {e}")
        return False