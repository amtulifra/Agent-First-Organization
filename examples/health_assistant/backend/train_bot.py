import os
import json
import time
import logging
import threading
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from arklex.utils.utils import init_logger
from arklex.orchestrator.orchestrator import AgentOrg
from arklex.orchestrator.generator.generator import Generator
from arklex.env.tools.RAG.build_rag import build_rag
from arklex.env.tools.database.build_database import build_database
from arklex.utils.model_config import MODEL

# Load environment variables
load_dotenv()

# Initialize a global logger for arklex-related logs
os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
logger = init_logger(
    log_level=logging.INFO,
    filename=os.path.join(os.path.dirname(__file__), "logs", "arklex.log")
)

# Create a custom handler to capture logs and forward to websocket
class WebSocketHandler(logging.Handler):
    def __init__(self, websocket=None):
        super().__init__()
        self.websocket = websocket
        self.formatter = logging.Formatter('%(message)s')
    
    def set_websocket(self, websocket):
        self.websocket = websocket
    
    def emit(self, record):
        if self.websocket:
            try:
                msg = self.format(record)
                level = record.levelname
                self.send_log(msg, level)
            except Exception:
                self.handleError(record)
    
    def send_log(self, message, level="INFO"):
        if self.websocket:
            try:
                self.websocket.send(json.dumps({
                    "action": "train_bot",
                    "status": "log",
                    "level": level,
                    "message": message
                }))
            except Exception as e:
                print(f"Error sending log to websocket: {e}")

# Create a global handler that can be used across modules
ws_handler = WebSocketHandler()

# Add the handler to the root logger to capture all logs
root_logger = logging.getLogger()
root_logger.addHandler(ws_handler)

# Add handler to the arklex logger
logging.getLogger("arklex").addHandler(ws_handler)

# Function to send logs to the websocket
def log_to_websocket(websocket, message, level="INFO"):
    if websocket:
        try:
            websocket.send(json.dumps({
                "action": "train_bot",
                "status": "log",
                "level": level,
                "message": message
            }))
        except Exception as e:
            print(f"Error sending log to websocket: {e}")

# Function to get user input
def get_user_input(websocket, prompt):
    """Ask the user for input and wait for their response"""
    if websocket:
        try:
            # Send prompt to user
            websocket.send(json.dumps({
                "action": "train_bot",
                "status": "input_required",
                "message": prompt
            }))
            
            # Wait for response
            response = None
            while response is None:
                try:
                    user_input = websocket.recv()
                    data = json.loads(user_input)
                    if data.get("action") == "provide_input":
                        response = data.get("input")
                        log_to_websocket(websocket, f"Received input: {response}", "INFO")
                except Exception as e:
                    log_to_websocket(websocket, f"Error processing input: {str(e)}", "ERROR")
                    return None
                
                # Wait a short time before checking again
                time.sleep(0.5)
            
            return response
        except Exception as e:
            print(f"Error getting user input: {e}")
            return None
    return None

# Class to mimic the args structure expected by Generator
class Args:
    def __init__(self, config_path, output_dir):
        self.config = config_path
        self.output_dir = output_dir

def generate_taskgraph(websocket, config_path, output_dir):
    """Generate task graph for the bot using the ArkLex Generator"""
    try:
        # Set the websocket handler
        ws_handler.set_websocket(websocket)
        
        # Create args object
        args = Args(config_path, output_dir)
        
        # Initialize the ChatOpenAI model
        model = ChatOpenAI(model=MODEL["model_type_or_path"], timeout=30000)
        
        # Create and run the Generator
        generator = Generator(args, args.config, model, args.output_dir)
        
        # Generate the task graph
        taskgraph_filepath = generator.generate()
        
        # Update the task graph with the API URLs
        task_graph_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), taskgraph_filepath)
        
        with open(task_graph_path, 'r') as f:
            task_graph = json.load(f)
        
        # Set empty API URLs directly without asking
        task_graph["nluapi"] = ""
        task_graph["slotfillapi"] = ""
        
        with open(task_graph_path, "w") as f:
            json.dump(task_graph, f, indent=4)
        
        return True
        
    except Exception as e:
        error_msg = f"Error generating task graph: {str(e)}"
        logger.error(error_msg)
        if websocket:
            websocket.send(json.dumps({
                "action": "train_bot",
                "status": "log",
                "level": "ERROR",
                "message": error_msg
            }))
        return False

def init_worker(websocket, config_path, output_dir):
    """Initialize workers for the bot using the ArkLex worker initialization"""
    try:
        # Set the websocket handler
        ws_handler.set_websocket(websocket)
        
        # Load the config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Create args object
        args = Args(config_path, output_dir)
        
        # Get the workers from the config
        workers = config.get("workers", [])
        worker_names = [worker.get("name") for worker in workers]
        
        # Check for RAG worker
        if "FaissRAGWorker" in worker_names:
            logger.info("Initializing FaissRAGWorker...")
            
            # Build RAG using the actual implementation
            rag_docs = config.get("rag_docs", [])
            
            # Build the RAG system directly without asking for max_docs
            build_rag(args.output_dir, rag_docs)
        
        # Check for database workers
        elif any(name in worker_names for name in ("DataBaseWorker", "search_show", "book_show", "check_booking", "cancel_booking")):
            logger.info("Initializing DatabaseWorker...")
            
            # Build database using the actual implementation
            build_database(args.output_dir)
        
        return True
        
    except Exception as e:
        error_msg = f"Error initializing workers: {str(e)}"
        logger.error(error_msg)
        if websocket:
            websocket.send(json.dumps({
                "action": "train_bot",
                "status": "log",
                "level": "ERROR",
                "message": error_msg
            }))
        return False

def train_bot(websocket, bot_name, task="all"):
    """Train a bot with the given name and task type"""
    try:
        # Set up paths
        project_root = Path(__file__).parent.parent
        kb_dir = project_root / "kb"
        bot_dir = kb_dir / bot_name
        config_path = str(bot_dir / "config.json")
        output_dir = str(bot_dir)
        
        # Set the websocket handler
        ws_handler.set_websocket(websocket)
        
        if not bot_dir.exists():
            error_msg = f"Bot directory not found: {bot_dir}"
            logger.error(error_msg)
            if websocket:
                websocket.send(json.dumps({
                    "action": "train_bot",
                    "status": "log",
                    "level": "ERROR",
                    "message": error_msg
                }))
            return False
            
        if not (bot_dir / "config.json").exists():
            error_msg = f"Config file not found for bot: {bot_name}"
            logger.error(error_msg)
            if websocket:
                websocket.send(json.dumps({
                    "action": "train_bot",
                    "status": "log",
                    "level": "ERROR",
                    "message": error_msg
                }))
            return False
        
        logger.info(f"Starting training process for bot: {bot_name}")
        logger.info(f"Task: {task}")
        logger.info(f"Config path: {config_path}")
        logger.info(f"Output directory: {output_dir}")
        
        success = True
        
        # Execute the requested tasks
        if task in ["all", "gen_taskgraph"]:
            logger.info("--- Generating Task Graph ---")
            success = generate_taskgraph(websocket, config_path, output_dir)
            if not success:
                return False
        
        if task in ["all", "init"]:
            logger.info("--- Initializing Workers ---")
            success = init_worker(websocket, config_path, output_dir)
            if not success:
                return False
        
        if success:
            logger.info(f"Bot {bot_name} trained successfully!")
            return True
        else:
            logger.error(f"Training failed for bot {bot_name}")
            return False
            
    except Exception as e:
        error_msg = f"Unexpected error during training: {str(e)}"
        logger.error(error_msg)
        if websocket:
            websocket.send(json.dumps({
                "action": "train_bot",
                "status": "log",
                "level": "ERROR",
                "message": error_msg
            }))
        return False

# Command-line interface for direct usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, default="./arklex/orchestrator/examples/customer_service_config.json")
    parser.add_argument('--output-dir', type=str, default="./examples/test")
    parser.add_argument('--model', type=str, default=MODEL["model_type_or_path"])
    parser.add_argument('--log-level', type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument('--task', type=str, choices=["gen_taskgraph", "init", "all"], default="all")
    parser.add_argument('--bot-name', type=str, help="Name of the bot to train")
    
    args = parser.parse_args()
    MODEL["model_type_or_path"] = args.model
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = init_logger(log_level=log_level, filename=os.path.join(os.path.dirname(__file__), "logs", "arklex.log"))

    if args.bot_name:
        # If bot name is provided, use the web interface compatible function
        class DummyWebSocket:
            def send(self, message):
                # Just print the message to console
                data = json.loads(message)
                if data.get("status") == "log":
                    print(f"[{data.get('level')}] {data.get('message')}")
            
            def recv(self):
                # This should never be called in the simplified version
                return None
        
        dummy_ws = DummyWebSocket()
        success = train_bot(dummy_ws, args.bot_name, args.task)
        if not success:
            print("Training failed")
            exit(1)
    else:
        # Use the original style functions for backward compatibility
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir, exist_ok=True)
        
        # Create args object
        arg_obj = Args(args.config, args.output_dir)
        
        if args.task == "all":
            # Original style function calls
            model = ChatOpenAI(model=MODEL["model_type_or_path"], timeout=30000)
            generator = Generator(arg_obj, arg_obj.config, model, arg_obj.output_dir)
            taskgraph_filepath = generator.generate()
            
            # Update the task graph with the API URLs
            task_graph = json.load(open(os.path.join(os.path.dirname(__file__), taskgraph_filepath)))
            task_graph["nluapi"] = ""
            task_graph["slotfillapi"] = ""
            with open(taskgraph_filepath, "w") as f:
                json.dump(task_graph, f, indent=4)
            
            # Initialize workers
            config = json.load(open(arg_obj.config))
            workers = config["workers"]
            worker_names = set([worker["name"] for worker in workers])
            if "FaissRAGWorker" in worker_names:
                logger.info("Initializing FaissRAGWorker...")
                build_rag(arg_obj.output_dir, config["rag_docs"])
            elif any(node in worker_names for name in ("DataBaseWorker", "search_show", "book_show", "check_booking", "cancel_booking")):
                logger.info("Initializing DatabaseWorker...")
                build_database(arg_obj.output_dir)
        
        elif args.task == "gen_taskgraph":
            model = ChatOpenAI(model=MODEL["model_type_or_path"], timeout=30000)
            generator = Generator(arg_obj, arg_obj.config, model, arg_obj.output_dir)
            taskgraph_filepath = generator.generate()
            
            # Update the task graph with the API URLs
            task_graph = json.load(open(os.path.join(os.path.dirname(__file__), taskgraph_filepath)))
            task_graph["nluapi"] = ""
            task_graph["slotfillapi"] = ""
            with open(taskgraph_filepath, "w") as f:
                json.dump(task_graph, f, indent=4)
        
        elif args.task == "init":
            config = json.load(open(arg_obj.config))
            workers = config["workers"]
            worker_names = set([worker["name"] for worker in workers])
            if "FaissRAGWorker" in worker_names:
                logger.info("Initializing FaissRAGWorker...")
                build_rag(arg_obj.output_dir, config["rag_docs"])
            elif any(node in worker_names for name in ("DataBaseWorker", "search_show", "book_show", "check_booking", "cancel_booking")):
                logger.info("Initializing DatabaseWorker...")
                build_database(arg_obj.output_dir) 