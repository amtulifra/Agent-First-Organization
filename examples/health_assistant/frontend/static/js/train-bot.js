document.addEventListener('DOMContentLoaded', function() {
    const botSelector = document.getElementById('bot-selector');
    const taskSelector = document.getElementById('task-selector');
    const trainBtn = document.getElementById('train-btn');
    const refreshBotsBtn = document.getElementById('refresh-bots-btn');
    const terminal = document.getElementById('terminal');
    const clearTerminalBtn = document.getElementById('clear-terminal-btn');
    const copyTerminalBtn = document.getElementById('copy-terminal-btn');
    const notification = document.getElementById('notification');
    const notificationMessage = document.querySelector('.notification-message');

    let ws = null;
    let isTraining = false;
    let inputPrompt = null;
    let inputDiv = null;

    // Initialize the page
    connectWebSocket();
    setupEventListeners();

    // Connect to WebSocket server
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8001`;
        
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log('WebSocket connection established');
            loadBots();
        };
        
        ws.onmessage = (event) => {
            const response = JSON.parse(event.data);
            handleServerResponse(response);
        };
        
        ws.onclose = () => {
            console.log('WebSocket connection closed');
            // Try to reconnect after a delay
            setTimeout(connectWebSocket, 3000);
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            showNotification('error', 'Failed to connect to server. Please try again later.');
        };
    }

    // Set up event listeners
    function setupEventListeners() {
        trainBtn.addEventListener('click', startTraining);
        refreshBotsBtn.addEventListener('click', loadBots);
        clearTerminalBtn.addEventListener('click', clearTerminal);
        copyTerminalBtn.addEventListener('click', copyTerminal);
    }

    // Load available bots
    function loadBots() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ 
                action: 'list_bots',
                only_config: true  // Only get bots with just a config file
            }));
            writeToTerminal('Fetching available bots...', 'terminal-blue');
        } else {
            console.log('WebSocket not connected, retrying in 1 second...');
            setTimeout(loadBots, 1000);
        }
    }

    // Start the training process
    function startTraining() {
        if (isTraining) {
            showNotification('error', 'Training is already in progress');
            return;
        }
        
        const selectedBot = botSelector.value;
        const selectedTask = taskSelector.value;
        
        if (!selectedBot) {
            showNotification('error', 'Please select a bot to train');
            return;
        }
        
        // Clear the terminal
        clearTerminal();
        
        // Send training request
        ws.send(JSON.stringify({
            action: 'train_bot',
            bot_name: selectedBot,
            task: selectedTask
        }));
        
        isTraining = true;
        updateUIForTraining(true);
        writeToTerminal(`Starting training for bot: ${selectedBot}`, 'terminal-green');
        writeToTerminal(`Task: ${getTaskDescription(selectedTask)}`, 'terminal-blue');
        writeToTerminal('Initializing training process...', 'terminal-yellow loading');
    }

    // Handle server response
    function handleServerResponse(response) {
        console.log('Received response:', response);
        
        if (response.action === 'list_bots') {
            updateBotsList(response.bots);
            writeToTerminal('Bot list updated successfully', 'terminal-green');
        } else if (response.action === 'train_bot') {
            if (response.status === 'completed') {
                writeToTerminal(response.message, 'terminal-green');
                isTraining = false;
                updateUIForTraining(false);
                showNotification('success', 'Bot training completed successfully');
                
                // Remove any input interface if it exists
                if (inputDiv) {
                    inputDiv.remove();
                    inputDiv = null;
                    inputPrompt = null;
                }
            } else if (response.status === 'error' || response.status === 'failed') {
                writeToTerminal('Error: ' + response.message, 'terminal-red');
                isTraining = false;
                updateUIForTraining(false);
                showNotification('error', response.message || 'Training failed');
                
                // Remove any input interface if it exists
                if (inputDiv) {
                    inputDiv.remove();
                    inputDiv = null;
                    inputPrompt = null;
                }
            } else if (response.status === 'log') {
                writeToTerminal(response.message, getLogClass(response.level));
            } else if (response.status === 'input_required') {
                // Create input interface for user
                createUserInputInterface(response.message);
            } else if (response.status === 'started') {
                writeToTerminal(response.message, 'terminal-blue');
            }
        }
    }

    // Update the bots dropdown list
    function updateBotsList(bots) {
        // Clear existing options
        botSelector.innerHTML = '';
        
        if (bots && bots.length > 0) {
            // Add default option
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.disabled = true;
            defaultOption.selected = true;
            defaultOption.textContent = 'Choose a bot...';
            botSelector.appendChild(defaultOption);
            
            // Add bots
            bots.forEach(bot => {
                const option = document.createElement('option');
                // Check if bot is a string (new format) or an object (old format)
                if (typeof bot === 'string') {
                    option.value = bot;
                    option.textContent = bot;
                } else {
                    option.value = bot.name;
                    option.textContent = bot.name;
                }
                botSelector.appendChild(option);
            });
        } else {
            // No bots available
            const noBotsOption = document.createElement('option');
            noBotsOption.value = '';
            noBotsOption.disabled = true;
            noBotsOption.selected = true;
            noBotsOption.textContent = 'No bots available - Create a bot first';
            botSelector.appendChild(noBotsOption);
        }
    }

    // Create user input interface
    function createUserInputInterface(prompt) {
        // Remove any existing input interface
        if (inputDiv) {
            inputDiv.remove();
        }
        
        // Create new input interface
        inputDiv = document.createElement('div');
        inputDiv.className = 'terminal-input-container';
        
        const promptElement = document.createElement('div');
        promptElement.className = 'terminal-prompt';
        promptElement.innerHTML = `<span class="terminal-yellow">${prompt}</span>`;
        
        const inputForm = document.createElement('form');
        inputForm.className = 'terminal-input-form';
        
        const inputElement = document.createElement('input');
        inputElement.type = 'text';
        inputElement.className = 'terminal-input';
        inputElement.placeholder = 'Type your response here...';
        inputElement.autocomplete = 'off';
        
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'terminal-input-submit';
        submitButton.textContent = 'Submit';
        
        inputForm.appendChild(inputElement);
        inputForm.appendChild(submitButton);
        
        inputDiv.appendChild(promptElement);
        inputDiv.appendChild(inputForm);
        
        // Add to terminal
        terminal.appendChild(inputDiv);
        
        // Focus on input
        inputElement.focus();
        
        // Scroll to bottom
        terminal.scrollTop = terminal.scrollHeight;
        
        // Handle form submission
        inputForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const userInput = inputElement.value.trim();
            if (userInput) {
                // Send user input to server
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        action: 'provide_input',
                        input: userInput
                    }));
                    
                    // Display user input in terminal
                    writeToTerminal(`> ${userInput}`, 'terminal-command');
                    
                    // Remove input interface
                    inputDiv.remove();
                    inputDiv = null;
                    inputPrompt = null;
                } else {
                    showNotification('error', 'Connection to server lost. Attempting to reconnect...');
                    connectWebSocket();
                }
            }
        });
        
        // Store current prompt
        inputPrompt = prompt;
    }

    // Write to terminal
    function writeToTerminal(text, className = '') {
        const now = new Date();
        const timeString = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
        
        // Create a new line element
        const line = document.createElement('div');
        line.className = 'terminal-line ' + className;
        
        // Add timestamp
        const timestamp = document.createElement('span');
        timestamp.className = 'time';
        timestamp.textContent = `[${timeString}]`;
        
        // Add the text
        const content = document.createElement('span');
        content.className = 'content';
        content.textContent = text;
        
        // Put it all together
        line.appendChild(timestamp);
        line.appendChild(content);
        
        // Add to terminal
        terminal.appendChild(line);
        
        // Scroll to bottom
        terminal.scrollTop = terminal.scrollHeight;
        
        // Remove loading class from previous elements if a new line is added
        const loadingElements = terminal.querySelectorAll('.loading');
        loadingElements.forEach(el => {
            if (el !== line) {
                el.classList.remove('loading');
            }
        });
    }

    // Clear terminal
    function clearTerminal() {
        terminal.innerHTML = '';
    }

    // Update UI based on training state
    function updateUIForTraining(isActive) {
        if (isActive) {
            trainBtn.disabled = true;
            refreshBotsBtn.disabled = true;
            botSelector.disabled = true;
            taskSelector.disabled = true;
            trainBtn.classList.add('training-in-progress');
            trainBtn.innerHTML = '<i class="fas fa-cogs"></i> Training in Progress...';
        } else {
            trainBtn.disabled = false;
            refreshBotsBtn.disabled = false;
            botSelector.disabled = false;
            taskSelector.disabled = false;
            trainBtn.classList.remove('training-in-progress');
            trainBtn.innerHTML = '<i class="fas fa-cogs"></i> Train Bot';
        }
    }

    // Get the appropriate class for log levels
    function getLogClass(level) {
        switch(level.toUpperCase()) {
            case 'INFO':
                return 'terminal-blue';
            case 'WARNING':
                return 'terminal-yellow';
            case 'ERROR':
            case 'CRITICAL':
                return 'terminal-red';
            case 'DEBUG':
                return '';
            default:
                return '';
        }
    }

    // Get task description
    function getTaskDescription(task) {
        switch(task) {
            case 'all':
                return 'All Tasks (Generate Task Graph + Initialize Workers)';
            case 'gen_taskgraph':
                return 'Generate Task Graph Only';
            case 'init':
                return 'Initialize Workers Only';
            default:
                return task;
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

    // Copy terminal content to clipboard
    function copyTerminal() {
        const text = terminal.innerText;
        
        navigator.clipboard.writeText(text)
            .then(() => {
                showNotification('success', 'Terminal output copied to clipboard');
            })
            .catch(err => {
                showNotification('error', 'Failed to copy terminal output');
                console.error('Could not copy text: ', err);
            });
    }
}); 