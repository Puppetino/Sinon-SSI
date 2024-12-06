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
});

// Control bot actions (start, restart, shutdown)
function controlBot(action) {
    console.log(`Control bot action initiated: ${action}`); // Debug log

    fetch('/api/control', {
        method: 'POST',
        credentials: 'same-origin', // Include session cookies
        body: new URLSearchParams({ action }),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
        .then(response => {
            console.log('Control bot response status:', response.status); // Debug log
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Control bot response data:', data); // Debug log
            alert(data.message || data.error);
        })
        .catch(error => {
            console.error('Error controlling bot:', error);
            alert('Error controlling bot: ' + error.message);
        });
}

// Fetch detailed streams
function fetchDetailedStreams() {
    fetch('/api/detailed_streams')
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('detailed-streams');
            tbody.innerHTML = ''; // Clear existing rows
            Object.values(data).forEach(stream => {
                const row = `<tr>
                    <td>${stream.streamer_name}</td>
                    <td>${stream.start_time}</td>
                    <td>${stream.end_time || 'Ongoing'}</td>
                    <td>${stream.peak_viewers}</td>
                    <td>${stream.duration}</td>
                </tr>`;
                tbody.innerHTML += row;
            });
        })
        .catch(error => console.error('Error fetching streams:', error));
}

// Authenticate the user
function authenticate() {
    const password = document.querySelector("input[name='password']").value;
    console.log('Password entered:', password); // Debug log

    fetch('/api/auth', {
        method: 'POST',
        body: new URLSearchParams({ password }),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
        .then(response => response.json())
        .then(data => {
            console.log('Authentication response:', data); // Debug log
            if (data.message) {
                alert(data.message);
                document.getElementById('auth-form').style.display = 'none';
                document.getElementById('control-buttons').style.display = 'block';
            } else {
                alert(data.error);
            }
        })
        .catch(error => console.error('Authentication error:', error));
}

document.getElementById('auth-form').addEventListener('submit', event => {
    event.preventDefault(); // Prevent form submission
    authenticate();         // Call the authenticate function
});

fetch('/api/check-auth', { credentials: 'same-origin' })
    .then(response => response.json())
    .then(data => console.log('Authenticated:', data.authenticated));