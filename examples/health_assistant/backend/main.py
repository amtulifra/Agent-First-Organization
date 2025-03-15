import os
import sys
import json
import logging
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
import websocket_server
from websocket_server import WebsocketServer

# Import the train_bot module and json_config
from train_bot import train_bot, ws_handler
from json_config import handle_config_creation
# Import the chatter module for chat sessions
from chatter import get_bot_response, get_welcome_message, close_session

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
                   datefmt='%m/%d/%Y %H:%M:%S')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/templates')
CORS(app)

# WebSocket server
websocket_clients = {}
websocket_server = None

# Dictionary to track active chat sessions by client ID
client_chat_sessions = {}

# Function to handle new WebSocket client connections
def new_client(client, server):
    logger.info(f"Client connected: {client['address']}")
    websocket_clients[client['id']] = client

# Function to handle client disconnections
def client_left(client, server):
    if client['id'] in websocket_clients:
        del websocket_clients[client['id']]
    
    # Close any active chat session for this client
    if client['id'] in client_chat_sessions:
        bot_name = client_chat_sessions[client['id']]
        logger.info(f"Closing chat session for bot {bot_name} due to client disconnect")
        close_session(bot_name)
        del client_chat_sessions[client['id']]
    
    logger.info(f"Client disconnected: {client['address']}")

# Function to handle messages from WebSocket clients
def message_received(client, server, message):
    logger.info(f"Received message: {message[:50]}...")
    try:
        data = json.loads(message)
        action = data.get('action')
        
        if action == 'create_config':
            # Handle bot configuration creation
            bot_name = data.get('bot_name')
            config_data = data.get('config')
            result = handle_config_creation(bot_name, config_data)
            server.send_message(client, json.dumps(result))
        
        elif action == 'list_bots':
            # List all available bots
            only_config = data.get('only_config', False)
            bots = list_bots(only_config)
            server.send_message(client, json.dumps({
                'action': 'list_bots',
                'bots': bots
            }))
        
        elif action == 'get_bot_details':
            # Get details for a specific bot
            bot_name = data.get('bot_name')
            if not bot_name:
                server.send_message(client, json.dumps({
                    'action': 'bot_details',
                    'valid': False,
                    'message': 'Bot name is required'
                }))
                return
            
            details = get_bot_details(bot_name)
            server.send_message(client, json.dumps(details))
        
        elif action == 'chat':
            # Handle chat with a bot using the chatter module
            bot_name = data.get('bot_name')
            message_text = data.get('message')
            
            if not bot_name or not message_text:
                server.send_message(client, json.dumps({
                    'action': 'chat_response',
                    'status': 'error',
                    'message': 'Bot name and message are required'
                }))
                return
            
            # Track the active chat session for this client
            client_chat_sessions[client['id']] = bot_name
            
            # Get response from the bot
            try:
                response, _ = get_bot_response(bot_name, message_text)
                server.send_message(client, json.dumps({
                    'action': 'chat_response',
                    'status': 'success',
                    'message': response
                }))
            except Exception as e:
                logger.error(f"Error getting bot response: {str(e)}")
                server.send_message(client, json.dumps({
                    'action': 'chat_response',
                    'status': 'error',
                    'message': f"Error: {str(e)}"
                }))
        
        elif action == 'select_bot':
            # Initialize a chat session when a bot is selected
            bot_name = data.get('bot_name')
            
            if not bot_name:
                server.send_message(client, json.dumps({
                    'action': 'select_bot',
                    'status': 'error',
                    'message': 'Bot name is required'
                }))
                return
            
            # Track the active chat session for this client
            client_chat_sessions[client['id']] = bot_name
            
            # Get the welcome message
            try:
                welcome_message = get_welcome_message(bot_name)
                server.send_message(client, json.dumps({
                    'action': 'select_bot',
                    'status': 'success',
                    'message': welcome_message
                }))
            except Exception as e:
                logger.error(f"Error initializing chat session: {str(e)}")
                server.send_message(client, json.dumps({
                    'action': 'select_bot',
                    'status': 'error',
                    'message': f"Error: {str(e)}"
                }))
        
        elif action == 'close_chat':
            # Close a chat session
            bot_name = data.get('bot_name')
            
            if not bot_name:
                server.send_message(client, json.dumps({
                    'action': 'close_chat',
                    'status': 'error',
                    'message': 'Bot name is required'
                }))
                return
            
            # Close the chat session
            if client['id'] in client_chat_sessions and client_chat_sessions[client['id']] == bot_name:
                success = close_session(bot_name)
                del client_chat_sessions[client['id']]
                
                server.send_message(client, json.dumps({
                    'action': 'close_chat',
                    'status': 'success' if success else 'error',
                    'message': 'Chat session closed' if success else 'Failed to close chat session'
                }))
        
        elif action == 'train_bot':
            # Start bot training in a separate thread
            bot_name = data.get('bot_name')
            task = data.get('task', 'all')
            
            if not bot_name:
                server.send_message(client, json.dumps({
                    'action': 'train_bot',
                    'status': 'error',
                    'message': 'Bot name is required'
                }))
                return
            
            # Start training in a separate thread
            threading.Thread(
                target=train_bot_thread,
                args=(client, server, bot_name, task),
                daemon=True
            ).start()
            
            # Send initial response
            server.send_message(client, json.dumps({
                'action': 'train_bot',
                'status': 'started',
                'message': f'Training started for bot: {bot_name}'
            }))
        
        elif action == 'provide_input':
            # Handle user input during training
            user_input = data.get('input')
            logger.info(f"Received user input for training process: {user_input[:20]}...")
            
            # Store the input in the client object for the WebSocketWrapper to retrieve
            client['input_message'] = json.dumps(data)
    
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON message: {message}")
        server.send_message(client, json.dumps({
            'action': 'error',
            'message': 'Invalid JSON message'
        }))
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        server.send_message(client, json.dumps({
            'action': 'error',
            'message': f'Error: {str(e)}'
        }))

# Function to run bot training in a separate thread
def train_bot_thread(client, server, bot_name, task):
    try:
        # Create a wrapper for the websocket to match the expected interface
        class WebSocketWrapper:
            def __init__(self, client, server):
                self.client = client
                self.server = server
            
            def send(self, message):
                self.server.send_message(self.client, message)
            
            def recv(self):
                # This is a blocking operation in the original code
                # We'll use a simple polling approach with a timeout
                start_time = time.time()
                timeout = 30000
                
                while time.time() - start_time < timeout:
                    # Check if there's a message in the client's queue
                    if hasattr(self.client, 'input_message'):
                        message = self.client.input_message
                        delattr(self.client, 'input_message')
                        return message
                    
                    # Sleep to avoid busy waiting
                    time.sleep(0.1)
                
                raise TimeoutError("Timeout waiting for user input")
        
        # Create a websocket wrapper
        ws_wrapper = WebSocketWrapper(client, server)
        
        # Run the training
        success = train_bot(ws_wrapper, bot_name, task)
        
        # Send completion message
        status = 'completed' if success else 'failed'
        server.send_message(client, json.dumps({
            'action': 'train_bot',
            'status': status,
            'message': f'Training {status} for bot: {bot_name}'
        }))
    
    except Exception as e:
        logger.error(f"Error in training thread: {str(e)}")
        server.send_message(client, json.dumps({
            'action': 'train_bot',
            'status': 'error',
            'message': f'Error: {str(e)}'
        }))

# Function to list all available bots
def list_bots(only_config_file=False):
    bots = []
    kb_dir = Path(__file__).parent.parent / 'kb'
    
    if kb_dir.exists():
        for bot_dir in kb_dir.iterdir():
            if bot_dir.is_dir() and (bot_dir / 'config.json').exists():
                # Check if we should only include bots with just a config file
                if only_config_file:
                    # Count files in the bot directory
                    file_count = sum(1 for _ in bot_dir.glob('*') if _.is_file())
                    # Only include if there's exactly 1 file (the config.json)
                    if file_count == 1:
                        bot_name = bot_dir.name
                        bots.append(bot_name)
                else:
                    bot_name = bot_dir.name
                    bots.append(bot_name)
    
    return bots

# Function to get bot details and validate it
def get_bot_details(bot_name):
    kb_dir = Path(__file__).parent.parent / 'kb'
    bot_dir = kb_dir / bot_name
    
    if not bot_dir.exists() or not bot_dir.is_dir():
        return {
            'action': 'bot_details',
            'valid': False,
            'bot_name': bot_name,
            'message': 'Bot directory not found',
            'file_count': 0
        }
    
    if not (bot_dir / 'config.json').exists():
        return {
            'action': 'bot_details',
            'valid': False,
            'bot_name': bot_name,
            'message': 'Config file not found',
            'file_count': 0
        }
    
    # Count files in the bot directory
    file_count = sum(1 for _ in bot_dir.glob('*') if _.is_file())
    
    # Read the config file to get additional info
    try:
        with open(bot_dir / 'config.json', 'r') as f:
            config = json.load(f)
        
        description = config.get('role', 'AI Assistant')
        
        return {
            'action': 'bot_details',
            'valid': True,
            'bot_name': bot_name,
            'description': description,
            'file_count': file_count,
            'message': 'Bot is valid'
        }
    except Exception as e:
        logger.warning(f"Error reading config for bot {bot_name}: {str(e)}")
        return {
            'action': 'bot_details',
            'valid': False,
            'bot_name': bot_name,
            'message': f'Error reading config: {str(e)}',
            'file_count': file_count
        }

# Flask routes
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('../frontend', path)

@app.after_request
def after_request(response):
    logger.info(f"{request.remote_addr} - \"{request.method} {request.path} HTTP/1.1\" {response.status_code} -")
    return response

# Function to start the WebSocket server
def start_websocket_server():
    global websocket_server
    
    # Create a WebSocket server
    websocket_server = WebsocketServer(host='0.0.0.0', port=8001)
    
    # Set up event handlers
    websocket_server.set_fn_new_client(new_client)
    websocket_server.set_fn_client_left(client_left)
    websocket_server.set_fn_message_received(message_received)
    
    # Start the server
    logger.info("WebSocket server started at ws://localhost:8001")
    websocket_server.run_forever()

# Function to start both servers
def start_servers():
    # Create kb directory if it doesn't exist
    kb_dir = Path(__file__).parent.parent / 'kb'
    kb_dir.mkdir(exist_ok=True)
    
    # Start WebSocket server in a separate thread
    websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
    websocket_thread.start()
    
    # Start Flask server
    logger.info("HTTP server started at http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)

# Main entry point
if __name__ == '__main__':
    logger.info("Starting ArkLex AI Chatbot Generator")
    
    try:
        start_servers()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running server: {str(e)}") 