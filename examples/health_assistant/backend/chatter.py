import os
import json
import time
import logging
import threading
from pathlib import Path
from dotenv import load_dotenv
from arklex.utils.utils import init_logger
from arklex.orchestrator.orchestrator import AgentOrg
from arklex.utils.model_config import MODEL
from arklex.utils.model_provider_config import LLM_PROVIDERS
from arklex.env.env import Env

# Load environment variables
load_dotenv()

# Initialize a global logger for arklex-related logs
os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
logger = init_logger(
    log_level=logging.INFO,
    filename=os.path.join(os.path.dirname(__file__), "logs", "arklex.log")
)

# Dictionary to store active chat sessions
active_sessions = {}

class ChatSession:
    """Class to manage a chat session with a bot"""
    def __init__(self, bot_name, model=MODEL["model_type_or_path"], llm_provider=MODEL["llm_provider"], log_level="INFO"):
        self.bot_name = bot_name
        self.history = []
        self.params = {}
        self.user_prefix = "user"
        self.worker_prefix = "assistant"
        
        # Set up model configuration
        MODEL["model_type_or_path"] = model
        MODEL["llm_provider"] = llm_provider
        
        # Set up logging
        log_level_num = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = init_logger(
            log_level=log_level_num, 
            filename=os.path.join(os.path.dirname(__file__), "logs", f"{bot_name}_chat.log")
        )
        
        # Set up paths
        project_root = Path(__file__).parent.parent
        kb_dir = project_root / "kb"
        bot_dir = kb_dir / bot_name
        self.config_path = str(bot_dir / "taskgraph.json")
        
        # Initialize environment and orchestrator
        try:
            self.logger.info(f"Initializing chat session for bot: {bot_name}")
            
            # Check if the bot directory and taskgraph exist
            if not bot_dir.exists() or not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Bot {bot_name} not found or taskgraph.json missing")
            
            # Load the config
            self.config = json.load(open(self.config_path))
            
            # Initialize environment
            self.env = Env(
                tools=self.config.get("tools", []),
                workers=self.config.get("workers", []),
                slotsfillapi=self.config.get("slotfillapi", "")
            )
            
            # Initialize orchestrator
            self.orchestrator = AgentOrg(config=self.config_path, env=self.env)
            
            # Get the start message from the config
            for node in self.config['nodes']:
                if node[1].get("type", "") == 'start':
                    start_message = node[1]['attribute']["value"]
                    break
            else:
                start_message = f"Hello! I'm {bot_name}. How can I help you today?"
            
            # Add the start message to the history
            self.history.append({"role": self.worker_prefix, "content": start_message})
            self.logger.info(f"Chat session initialized with start message: {start_message}")
            
            self.is_active = True
        except Exception as e:
            self.logger.error(f"Error initializing chat session: {str(e)}")
            raise

    def get_response(self, user_text):
        """Get a response from the bot for the given user text"""
        try:
            if not self.is_active:
                return "Chat session has been closed.", {}
            
            start_time = time.time()
            self.logger.info(f"Processing user message: {user_text}")
            
            # Prepare the data for the orchestrator
            data = {
                "text": user_text, 
                'chat_history': self.history, 
                'parameters': self.params
            }
            
            # Get the response from the orchestrator
            result = self.orchestrator.get_response(data)
            
            # Update the history and parameters
            self.history.append({"role": self.user_prefix, "content": user_text})
            self.history.append({"role": self.worker_prefix, "content": result['answer']})
            self.params = result['parameters']
            
            self.logger.info(f"Response time: {time.time() - start_time:.2f}s")
            self.logger.info(f"Bot response: {result['answer']}")
            
            return result['answer'], self.params
        except Exception as e:
            error_msg = f"Error getting response: {str(e)}"
            self.logger.error(error_msg)
            return f"I'm sorry, but I encountered an error: {str(e)}", self.params

    def close(self):
        """Close the chat session and clean up resources"""
        try:
            self.logger.info(f"Closing chat session for bot: {self.bot_name}")
            self.is_active = False
            # Clean up any resources if needed
            return True
        except Exception as e:
            self.logger.error(f"Error closing chat session: {str(e)}")
            return False


def get_or_create_session(bot_name):
    """Get an existing session or create a new one"""
    if bot_name in active_sessions and active_sessions[bot_name].is_active:
        return active_sessions[bot_name]
    
    # Create a new session
    session = ChatSession(bot_name)
    active_sessions[bot_name] = session
    return session


def close_session(bot_name):
    """Close a chat session"""
    if bot_name in active_sessions:
        success = active_sessions[bot_name].close()
        if success:
            del active_sessions[bot_name]
        return success
    return False


def get_bot_response(bot_name, user_text):
    """Get a response from the bot for the given user text"""
    try:
        session = get_or_create_session(bot_name)
        return session.get_response(user_text)
    except Exception as e:
        logger.error(f"Error in get_bot_response: {str(e)}")
        return f"Error: {str(e)}", {}


def get_welcome_message(bot_name):
    """Get the welcome message for a bot"""
    try:
        session = get_or_create_session(bot_name)
        # Return the first message in the history (which should be the welcome message)
        if session.history:
            return session.history[0]["content"]
        return f"Hello! I'm {bot_name}. How can I help you today?"
    except Exception as e:
        logger.error(f"Error getting welcome message: {str(e)}")
        return f"Hello! I'm {bot_name}. How can I help you today?"


# For testing purposes
if __name__ == "__main__":
    bot_name = "test_bot"
    session = get_or_create_session(bot_name)
    
    try:
        while True:
            user_text = input("You: ")
            if user_text.lower() == "quit":
                break
            
            response, _ = session.get_response(user_text)
            print(f"Bot: {response}")
    finally:
        session.close() 