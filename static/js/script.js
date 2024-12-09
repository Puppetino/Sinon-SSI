// Control bot actions (start, restart, shutdown)
function controlBot(action) {
    console.log(`Control bot action initiated: ${action}`); // Debug log

    fetch('/api/control', {
        method: 'POST',
        credentials: 'same-origin',
        body: new URLSearchParams({ action }),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }).catch(error => console.error('Error controlling bot:', error));
}

// Fetch detailed streams and render them
function fetchDetailedStreams() {
    fetch('/api/detailed_streams')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('streams-container');
            container.innerHTML = ''; // Clear existing cards

            Object.values(data).forEach(stream => {
                const card = document.createElement('div');
                card.className = 'stream-card';

                const thumbnail = document.createElement('img');
                thumbnail.src = stream.thumbnail_url || 'default-thumbnail.png';
                card.appendChild(thumbnail);

                const content = document.createElement('div');
                content.className = 'stream-card-content';

                const title = document.createElement('h3');
                title.textContent = stream.title || 'Untitled Stream';
                content.appendChild(title);

                const streamer = document.createElement('p');
                streamer.textContent = `Streamer: ${stream.streamer_name}`;
                content.appendChild(streamer);

                const maxViewers = document.createElement('p');
                maxViewers.textContent = `Max Viewers: ${stream.peak_viewers || 'N/A'}`;
                content.appendChild(maxViewers);

                const startTime = document.createElement('p');
                startTime.textContent = `Start Time: ${stream.start_time || 'Unknown'}`;
                content.appendChild(startTime);

                const endTime = document.createElement('p');
                endTime.textContent = `End Time: ${stream.end_time || 'Ongoing'}`;
                content.appendChild(endTime);

                const duration = document.createElement('p');
                duration.textContent = `Duration: ${stream.duration || 'N/A'}`;
                content.appendChild(duration);

                card.appendChild(content);
                container.appendChild(card);
            });
        })
        .catch(error => console.error('Error fetching streams:', error));
}

// Authenticate the user
function authenticate() {
    const password = document.querySelector("input[name='password']").value;
    const authButton = document.querySelector("#auth-form button");
    authButton.disabled = true; // Disable button to prevent duplicate submissions

    fetch('/api/auth', {
        method: 'POST',
        body: new URLSearchParams({ password }),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
        .then(response => response.json())
        .then(data => {
            console.log('Authentication response:', data);
            if (data.message) {
                alert(data.message);
                document.getElementById('auth-form').classList.add('hidden');
                document.getElementById('control-buttons').classList.remove('hidden');
            } else {
                alert(data.error);
            }
        })
        .catch(error => console.error('Authentication error:', error))
        .finally(() => {
            authButton.disabled = false; // Re-enable the button
        });
}

// Update bot status and UI dynamically
function updateBotStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            const statusText = document.getElementById('status-text');
            const statusIndicator = document.getElementById('status-indicator');
            const botStatus = data.status;

            // Update status text and CSS classes
            statusText.textContent = botStatus.charAt(0).toUpperCase() + botStatus.slice(1);
            document.body.classList.remove('bot-online', 'bot-offline', 'bot-starting', 'bot-restarting', 'bot-shutting-down');
            document.body.classList.add(`bot-${botStatus.replace(/\s/g, '-')}`); // Add class dynamically
        })
        .catch(error => console.error('Error fetching bot status:', error));
}

// Attach all event listeners after DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM fully loaded and parsed'); // Debug log

    // Attach listener to the authentication form
    const authForm = document.getElementById('auth-form');
    authForm.addEventListener('submit', (event) => {
        event.preventDefault(); // Prevent page reload
        console.log('Authentication form submitted'); // Debug log
        authenticate();
    });

    // Attach listeners to control buttons
    const controlButtons = document.getElementById('control-buttons');
    controlButtons.addEventListener('click', (event) => {
        const action = event.target.dataset.action;
        if (action) {
            console.log(`Control button clicked: ${action}`); // Debug log
            controlBot(action);
        }
    });

    // Attach toggle functionality to section divs
    document.querySelectorAll('.section').forEach(section => {
        section.addEventListener('click', (event) => {
            if (event.target.matches('input, button, textarea')) {
                return; // Ignore clicks on interactive elements
            }
            const content = section.querySelector('.content');
            content.classList.toggle('hidden');
        });
    });

    // Attach light/dark mode toggle
    const toggleButton = document.getElementById('theme-toggle');
    toggleButton.addEventListener('click', () => {
        document.body.classList.toggle('light-mode');
        toggleButton.textContent = document.body.classList.contains('light-mode')
            ? "Toggle Dark Mode"
            : "Toggle Light Mode";
    });

    // Initial fetch for bot status and streams
    updateBotStatus();
    fetchDetailedStreams();

    // Set up periodic updates
    setInterval(updateBotStatus, 5000);
    setInterval(fetchDetailedStreams, 30000);
});