document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('create-bot-form');
    const saveBtn = document.getElementById('save-btn');
    const resetBtn = document.getElementById('reset-btn');
    const notification = document.getElementById('notification');
    const notificationMessage = document.querySelector('.notification-message');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const addTaskDocBtn = document.getElementById('add-task-doc');
    const addRagDocBtn = document.getElementById('add-rag-doc');
    const taskDocsContainer = document.getElementById('task-docs-container');
    const ragDocsContainer = document.getElementById('rag-docs-container');

    let ws = null;

    // Connect to WebSocket server
    function connectWebSocket() {
        ws = new WebSocket(`ws://localhost:8001`);
        
        ws.onopen = function() {
            console.log('WebSocket connection established');
        };
        
        ws.onmessage = function(event) {
            const response = JSON.parse(event.data);
            handleServerResponse(response);
        };
        
        ws.onerror = function(error) {
            console.error('WebSocket error:', error);
            showNotification('error', 'Failed to connect to server. Please try again later.');
        };
        
        ws.onclose = function() {
            console.log('WebSocket connection closed');
            // Try to reconnect after 5 seconds
            setTimeout(connectWebSocket, 5000);
        };
    }

    // Initialize WebSocket connection
    connectWebSocket();

    // Handle tab switching
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Update active state for buttons
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Show the selected tab content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === tabId) {
                    content.classList.add('active');
                }
            });
        });
    });

    // Handle document source addition
    addTaskDocBtn.addEventListener('click', () => addDocItem(taskDocsContainer, 'task'));
    addRagDocBtn.addEventListener('click', () => addDocItem(ragDocsContainer, 'rag'));

    // Set up remove document event delegation
    document.addEventListener('click', function(e) {
        if (e.target.closest('.remove-doc-btn')) {
            const docItem = e.target.closest('.doc-item');
            const container = docItem.parentElement;
            
            // Ensure we keep at least one document source
            if (container.querySelectorAll('.doc-item').length > 1) {
                docItem.remove();
            } else {
                showNotification('error', 'You must have at least one document source');
            }
        }
    });

    // Save button click handler
    saveBtn.addEventListener('click', function() {
        if (validateForm()) {
            const botData = collectFormData();
            sendBotData(botData);
        }
    });

    // Reset form button
    resetBtn.addEventListener('click', function() {
        if (confirm('Are you sure you want to reset the form? All changes will be lost.')) {
            form.reset();
        }
    });

    // Function to add a new document item
    function addDocItem(container, prefix) {
        const newItem = document.createElement('div');
        newItem.className = 'doc-item';
        newItem.innerHTML = `
            <div class="form-group">
                <label>Source URL</label>
                <input type="url" class="doc-source" name="${prefix}-doc-source[]" placeholder="https://example.com">
            </div>
            <div class="form-group">
                <label>Description</label>
                <input type="text" class="doc-desc" name="${prefix}-doc-desc[]" placeholder="Description of the source">
            </div>
            <div class="form-group">
                <label>Number of Documents</label>
                <input type="number" class="doc-num" name="${prefix}-doc-num[]" min="1" value="1">
            </div>
            <button type="button" class="remove-doc-btn"><i class="fas fa-trash"></i></button>
        `;
        container.appendChild(newItem);
    }

    // Function to validate the form
    function validateForm() {
        const botName = document.getElementById('bot-name').value.trim();
        const role = document.getElementById('role').value.trim();
        const domain = document.getElementById('domain').value.trim();
        const userObjective = document.getElementById('user-objective').value.trim();
        const builderObjective = document.getElementById('builder-objective').value.trim();
        const intro = document.getElementById('intro').value.trim();
        
        if (!botName) {
            showNotification('error', 'Bot name is required');
            return false;
        }
        
        if (!role) {
            showNotification('error', 'Role is required');
            return false;
        }
        
        if (!domain) {
            showNotification('error', 'Domain is required');
            return false;
        }
        
        if (!userObjective) {
            showNotification('error', 'User objective is required');
            return false;
        }
        
        if (!builderObjective) {
            showNotification('error', 'Builder objective is required');
            return false;
        }
        
        if (!intro) {
            showNotification('error', 'Introduction message is required');
            return false;
        }
        
        return true;
    }

    // Function to collect form data
    function collectFormData() {
        const botName = document.getElementById('bot-name').value.trim();
        
        // Collect task documents
        const taskDocs = [];
        const taskDocItems = taskDocsContainer.querySelectorAll('.doc-item');
        taskDocItems.forEach(item => {
            const source = item.querySelector('.doc-source').value;
            const desc = item.querySelector('.doc-desc').value;
            const num = parseInt(item.querySelector('.doc-num').value, 10);
            
            if (source && desc) {
                taskDocs.push({ source, desc, num });
            }
        });
        
        // Collect RAG documents
        const ragDocs = [];
        const ragDocItems = ragDocsContainer.querySelectorAll('.doc-item');
        ragDocItems.forEach(item => {
            const source = item.querySelector('.doc-source').value;
            const desc = item.querySelector('.doc-desc').value;
            const num = parseInt(item.querySelector('.doc-num').value, 10);
            
            if (source && desc) {
                ragDocs.push({ source, desc, num });
            }
        });
        
        // Collect workers
        const workers = [];
        const workerItems = document.querySelectorAll('.worker-item');
        workerItems.forEach(item => {
            const name = item.querySelector('.worker-name').value;
            const path = item.querySelector('.worker-path').value;
            const id = item.querySelector('.worker-id').value;
            
            workers.push({ id, name, path });
        });
        
        return {
            action: 'create_config',
            bot_name: botName,
            config: {
                role: document.getElementById('role').value,
                user_objective: document.getElementById('user-objective').value,
                builder_objective: document.getElementById('builder-objective').value,
                domain: document.getElementById('domain').value,
                intro: document.getElementById('intro').value,
                task_docs: taskDocs,
                rag_docs: ragDocs,
                tasks: [],
                tools: [],
                workers: workers
            }
        };
    }

    // Function to send bot data to server
    function sendBotData(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
            showNotification('success', 'Processing your request...');
        } else {
            showNotification('error', 'Connection to server lost. Attempting to reconnect...');
            connectWebSocket();
        }
    }

    // Function to handle server response
    function handleServerResponse(response) {
        if (response.status === 'success') {
            showNotification('success', response.message);
            // Redirect to train-bot page after successful creation
            setTimeout(() => {
                window.location.href = 'train-bot.html';
            }, 1500);
        } else {
            showNotification('error', response.message || 'An unknown error occurred');
        }
    }

    // Function to show notification
    function showNotification(type, message) {
        notification.className = 'notification show ' + type;
        notificationMessage.textContent = message;
        
        // Hide notification after 5 seconds
        setTimeout(() => {
            notification.classList.remove('show');
        }, 5000);
    }
}); 