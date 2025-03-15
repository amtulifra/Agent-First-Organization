A comprehensive web app for creating, training, and deploying sophisticated AI chatbots using the ArkLex framework. This platform provides an end-to-end solution for building conversational agents with advanced natural language understanding capabilities.

##Overview

## Key Features

- **Intuitive Bot Creation**: User-friendly interface for configuring chatbots with custom roles, domains, and objectives
- **Advanced Training Pipeline**: Real-time training process with live terminal output and interactive user input
- **Knowledge Integration**: Seamless incorporation of various knowledge sources for enhanced bot intelligence
- **Modular Architecture**: Worker-based system allowing for specialized bot capabilities
- **Real-time Chat Interface**: WebSocket-powered chat experience with persistent sessions
- **Responsive Design**: Professional UI that works across desktop and mobile devices
- **Session Management**: Robust handling of chat sessions with proper resource allocation and cleanup

## Project Architecture

```
.
├── backend/                # Server-side Python code
│   ├── main.py             # Main server entry point with WebSocket and HTTP servers
│   ├── json_config.py      # Configuration file generation and management
│   ├── train_bot.py        # Bot training orchestration module
│   ├── chatter.py          # Chat session management system
│   └── logs/               # Server and training logs
├── frontend/               # Client-side web interface
│   ├── index.html          # Landing page with platform overview
│   ├── create-bot.html     # Comprehensive bot configuration interface
│   ├── train-bot.html      # Interactive training console with real-time feedback
│   ├── chat.html           # Advanced chat interface for bot interaction
│   └── static/             # Static assets
│       ├── css/            # Stylesheets including responsive design
│       ├── js/             # Client-side JavaScript for dynamic interactions
│       └── images/         # Visual assets and branding elements
├── kb/                     # Knowledge base directory
│   └── [bot_name]/         # Bot-specific directories containing:
│       ├── config.json     # Bot configuration
│       ├── taskgraph.json  # Generated conversation flow
│       ├── vector_store/   # Embeddings for knowledge retrieval
│       └── database/       # Structured data storage (when applicable)
├── requirements.txt        # Python dependencies
└── readme.md               # Project documentation
```
