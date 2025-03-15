import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def handle_config_creation(bot_name, config_data):
    if not bot_name:
        return {"status": "error", "message": "Bot name is required"}
    
    # Sanitize bot name for folder name (remove special characters)
    safe_bot_name = "".join(c for c in bot_name if c.isalnum() or c in [' ', '_']).strip().replace(' ', '_')
    
    if not safe_bot_name:
        return {"status": "error", "message": "Invalid bot name"}
    
    # Create bot directory in kb folder
    project_root = Path(__file__).parent.parent
    bot_dir = project_root / "kb" / safe_bot_name
    bot_dir.mkdir(exist_ok=True, parents=True)
    
    # Construct the full path for config.json
    config_path = bot_dir / "config.json"
    
    try:
        # Add bot name to config data
        if "name" not in config_data:
            config_data["name"] = bot_name
        
        # Write the config.json file
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Successfully created config for bot: {bot_name}")
        return {
            "status": "success", 
            "message": f"Bot '{bot_name}' configuration created successfully",
            "config_path": str(config_path)
        }
    except Exception as e:
        logger.error(f"Error creating config for bot {bot_name}: {str(e)}")
        return {"status": "error", "message": f"Failed to create bot configuration: {str(e)}"}

def get_default_config():
    return {
        "role": "healthcare assistant",
        "user_objective": "The healthcare assistant helps users understand medical conditions, assess symptoms, find preventive care information, and navigate healthcare resources. It provides evidence-based health information while emphasizing the importance of consulting healthcare professionals for personalized medical advice.",
        "builder_objective": "The healthcare assistant collects relevant health information to provide accurate guidance and always includes appropriate medical disclaimers, emphasizing that it is not a substitute for professional medical care.",
        "domain": "healthcare and medicine",
        "intro": "This healthcare assistant provides evidence-based information on common medical conditions, symptoms, treatments, preventive measures, and healthy lifestyle recommendations. It can help users understand general health concepts, interpret medical terminology, and determine when to seek professional medical care. The assistant emphasizes that it provides general information only and is not a replacement for consultation with qualified healthcare providers who can provide personalized medical advice based on individual circumstances.",
        "task_docs": [
            {
                "source": "https://medlineplus.gov/",
                "desc": "MedlinePlus is a service of the National Library of Medicine providing reliable, up-to-date health information",
                "num": 2
            },
            {
                "source": "https://www.cdc.gov/",
                "desc": "Centers for Disease Control and Prevention provides health information and disease prevention guidelines",
                "num": 2
            }
        ],
        "rag_docs": [
            {
                "source": "https://medlineplus.gov/",
                "desc": "MedlinePlus is a service of the National Library of Medicine providing reliable, up-to-date health information",
                "num": 2
            },
            {
                "source": "https://www.cdc.gov/",
                "desc": "Centers for Disease Control and Prevention provides health information and disease prevention guidelines",
                "num": 2
            }
        ],
        "tasks": [],
        "tools": [],
        "workers": [
            {"id": "26bb6634-3bee-417d-ad72-23269ac17bc3", "name": "MessageWorker", "path": "message_worker.py"},
            {"id": "9c12af81-04b3-443e-be04-a3222124b902", "name": "SearchWorker", "path": "search_worker.py"},
            {"id": "f9ddf676-b822-4439-b9a2-42026c7634a3", "name": "FaissRAGWorker", "path": "faiss_rag_worker.py"},
            {"id": "b06c2b28-12c2-41fe-9838-e93b230e42e8", "name": "DefaultWorker", "path": "default_worker.py"}
        ]
    } 