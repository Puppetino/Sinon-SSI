from flask import Flask, render_template, jsonify, request, session
from flask_talisman import Talisman
from dotenv import load_dotenv
from flask_cors import CORS
import subprocess
import time
import json
import os

load_dotenv()   # Load environment variables

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")    # Add a strong secret key
Talisman(app)                                                           # Enable Content Security Policy
CORS(app, supports_credentials=True)                                    # Enable CORS

# Data folder path
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')           # Define the path to your Data folder
BOT_SCRIPT = os.path.join(os.path.dirname(__file__), 'bot.py')          # Path to the bot script

# Track the bot process and status
bot_process = None
bot_status = "offline"

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
    stats_file = os.path.join(DATA_FOLDER, 'stats.json')
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as file:
            stats = json.load(file)
    else:
        stats = {}

    return render_template(
        'index.html',
        channel_settings=channel_settings,
        role_permissions=role_permissions,
        targets=targets,
        stats=stats
    )

# API route to fetch data (optional for AJAX requests)
@app.route('/api/stats')
def api_stats():
    data = {
        "channel_settings": load_json('channel_settings.json'),
        "role_permissions": load_json('role_permission.json'),
        "targets": load_json('targets.json')
    }

    # Load stats.json and include in the response
    stats_file = os.path.join(DATA_FOLDER, "stats.json")
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as file:
            data["stats"] = json.load(file)
    else:
        data["stats"] = {}

    return jsonify(data)

# API route to fetch detailed streams
@app.route('/api/detailed_streams', methods=['GET'])
def detailed_streams():
    stats_file = os.path.join(DATA_FOLDER, 'stats.json')
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as file:
            stats = json.load(file)
            detailed_streams = stats.get("detailed_streams", {})
            # Add additional processing if necessary
            return jsonify(detailed_streams)
    return jsonify({})

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
        if "python3" in result.stdout:
            bot_status = "online"
        else:
            bot_status = "offline"
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
        # Check if the bot is already running in the Sinon tmux session
        result = subprocess.run(
            ["tmux", "list-panes", "-t", "Sinon", "-F", "#{pane_current_command}"],
            capture_output=True,
            text=True,
            check=True,
        )
        if "python3" in result.stdout:
            bot_status = "online"
            return jsonify({"message": "Bot is already running in the Sinon session."}), 400
    except subprocess.CalledProcessError:
        pass  # No existing session; proceed to start

    # Start the bot process in the existing Sinon tmux session
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", "Sinon", "python3 bot.py", "C-m"],
            check=True,
        )
        bot_status = "online"  # Update status
        return jsonify({"message": "Bot is starting in the Sinon tmux session."}), 200
    except Exception as e:
        bot_status = "offline"  # Ensure status reflects failure
        return jsonify({"error": f"Error starting the bot: {e}"}), 500

# Functions to stop the bot
def shutdown_bot():
    global bot_status
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", "Sinon", "C-c"],
            check=True,
        )
        bot_status = "offline"  # Update status
        return jsonify({"message": "Bot has been stopped in the Sinon tmux session."}), 200
    except subprocess.CalledProcessError:
        bot_status = "offline"  # Ensure status reflects failure
        return jsonify({"error": "Bot is not running or tmux session not found."}), 400
    except Exception as e:
        return jsonify({"error": f"Error shutting down the bot: {e}"}), 500

# Functions to restart the bot
def restart_bot():
    global bot_status
    shutdown_response = shutdown_bot()
    if shutdown_response[1] != 200:  # If shutdown failed, return the error
        return shutdown_response

    time.sleep(1)  # Ensure shutdown completes
    start_response = start_bot()
    bot_status = "online" if start_response[1] == 200 else "offline"
    return start_response

# API route to check authentication
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    return jsonify({"authenticated": session.get('authenticated', False)})

# Favicon
@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

# Security
@app.after_request
def remove_security_headers(response):
    return response

# Content Security Policy
@app.after_request
def add_relaxed_security_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
    )
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)