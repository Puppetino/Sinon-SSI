from flask import Flask, render_template, jsonify, request, session
from flask_talisman import Talisman
from dotenv import load_dotenv
from flask_cors import CORS
import subprocess
import time
import json
import os

load_dotenv()  # Load environment variables

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")  # Add a strong secret key
Talisman(app)  # Enable Content Security Policy
CORS(app, supports_credentials=True)  # Enable CORS

# Paths
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')  # Define the path to your Data folder
STATS_FILE = os.path.join(DATA_FOLDER, 'stats.json')
TARGETS_FILE = os.path.join(DATA_FOLDER, 'targets.json')
BOT_SCRIPT = os.path.join(os.path.dirname(__file__), 'bot.py')  # Path to the bot script

# Default file structures
DEFAULT_STATS = {
    "streams_checked": 0,
    "active_streams": 0,
    "guilds_tracked": 0,
    "messages_sent": 0,
    "detailed_streams": {}
}
DEFAULT_TARGETS = {
    "active_targets": [],
    "past_targets": []
}

# Track the bot process and status
bot_process = None
bot_status = "offline"

# Function to ensure files exist with default content
def ensure_file_exists(file_path, default_content):
    """Ensure a JSON file exists and is properly initialized."""
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)  # Create the data folder if it doesn't exist

    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            json.dump(default_content, file, indent=4)
    else:
        try:
            # Attempt to load the JSON to ensure it's valid
            with open(file_path, 'r') as file:
                json.load(file)
        except (json.JSONDecodeError, IOError):
            # Reinitialize the file if it's corrupted
            with open(file_path, 'w') as file:
                json.dump(default_content, file, indent=4)

# Ensure critical files are initialized
ensure_file_exists(STATS_FILE, DEFAULT_STATS)
ensure_file_exists(TARGETS_FILE, DEFAULT_TARGETS)

# Authentication
@app.route('/api/auth', methods=['POST'])
def authenticate():
    password = request.form.get('password')
    if password == os.getenv('ADMIN_PASSWORD', 'default_password'):
        session['authenticated'] = True
        return jsonify({"message": "Authentication successful"}), 200
    return jsonify({"error": "Unauthorized"}), 403

# Load data from JSON files
def load_json(file_name):
    file_path = os.path.join(DATA_FOLDER, file_name)
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    return {}

# Home route
@app.route('/')
def home():
    # Load data to pass to the HTML template
    channel_settings = load_json('channel_settings.json')
    role_permissions = load_json('role_permission.json')
    targets = load_json('targets.json')

    # Load stats from stats.json
    stats = load_json('stats.json')

    return render_template(
        'index.html',
        channel_settings=channel_settings,
        role_permissions=role_permissions,
        targets=targets,
        stats=stats
    )

# API route to fetch data
@app.route('/api/stats')
def api_stats():
    return jsonify({
        "channel_settings": load_json('channel_settings.json'),
        "role_permissions": load_json('role_permission.json'),
        "targets": load_json('targets.json'),
        "stats": load_json('stats.json'),
    })

# API route to fetch detailed streams
@app.route('/api/detailed_streams', methods=['GET'])
def detailed_streams():
    stats = load_json('stats.json')
    return jsonify(stats.get("detailed_streams", {}))

@app.route('/api/status', methods=['GET'])
def bot_status_endpoint():
    global bot_status
    try:
        # Check if the bot is running in the Sinon tmux session
        result = subprocess.run(
            ["tmux", "list-panes", "-t", "Sinon", "-F", "#{pane_current_command}"],
            capture_output=True,
            text=True,
            check=True,
        )
        bot_status = "online" if "python3" in result.stdout else "offline"
    except subprocess.CalledProcessError:
        bot_status = "offline"
    return jsonify({"status": bot_status})

# API route to control the bot
@app.route('/api/control', methods=['POST'])
def control_bot():
    if not session.get('authenticated'):
        return jsonify({"error": "Unauthorized"}), 403

    action = request.form.get('action')

    if action == "start":
        return start_bot()

    elif action == "restart":
        return restart_bot()

    elif action == "shutdown":
        return shutdown_bot()

    return jsonify({"error": "Invalid action"}), 400

# Functions to start the bot
def start_bot():
    global bot_status
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", "Sinon", "-F", "#{pane_current_command}"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "python3" in result.stdout:
            bot_status = "online"
            return jsonify({"message": "Bot is already running."}), 400
    except subprocess.CalledProcessError:
        pass

    try:
        subprocess.run(["tmux", "send-keys", "-t", "Sinon", "python3 bot.py", "C-m"], check=True)
        bot_status = "online"
        return jsonify({"message": "Bot is starting."}), 200
    except Exception as e:
        bot_status = "offline"
        return jsonify({"error": f"Error starting the bot: {e}"}), 500

# Functions to stop the bot
def shutdown_bot():
    global bot_status
    try:
        subprocess.run(["tmux", "send-keys", "-t", "Sinon", "C-c"], check=True)
        bot_status = "offline"
        return jsonify({"message": "Bot has been stopped."}), 200
    except subprocess.CalledProcessError:
        bot_status = "offline"
        return jsonify({"error": "Bot is not running or tmux session not found."}), 400
    except Exception as e:
        return jsonify({"error": f"Error shutting down the bot: {e}"}), 500

# Functions to restart the bot
def restart_bot():
    global bot_status
    shutdown_response = shutdown_bot()
    if shutdown_response[1] != 200:
        return shutdown_response

    time.sleep(1)
    start_response = start_bot()
    bot_status = "online" if start_response[1] == 200 else "offline"
    return start_response

# API route to check authentication
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    return jsonify({"authenticated": session.get('authenticated', False)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)