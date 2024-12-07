from flask import Flask, render_template, jsonify, request, session
from dotenv import load_dotenv
import platform
import subprocess
import json
import os
from flask_talisman import Talisman
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default_secret_key")  # Add a strong secret key
Talisman(app)
CORS(app, supports_credentials=True)

DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')   # Define the path to your Data folder
BOT_SCRIPT = os.path.join(os.path.dirname(__file__), 'bot.py')  # Path to the bot script

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
        stats = {}  # Default empty stats if the file doesn't exist

    return render_template(
        'index.html',
        channel_settings=channel_settings,
        role_permissions=role_permissions,
        targets=targets,
        stats=stats  # Pass stats to the template
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
    return jsonify({"status": bot_status})

@app.route('/api/control', methods=['POST'])
def control_bot():
    global bot_process, bot_status

    action = request.form.get('action')
    os_type = platform.system()  # Determine the OS (Windows, Linux, etc.)
    bot_status = "offline" if not bot_process or bot_process.poll() is not None else bot_status

    if action == "start":
        if bot_status == "online":
            return jsonify({"message": "Bot is already running."}), 400

        bot_status = "starting"
        if os_type == "Windows":
            # Start the bot on Windows
            if not bot_process or bot_process.poll() is not None:
                bot_process = subprocess.Popen(["python", BOT_SCRIPT], creationflags=subprocess.CREATE_NEW_CONSOLE)
            bot_status = "online"
        elif os_type == "Linux":
            # Start the bot in the tmux session on Linux
            session_exists = subprocess.run(
                ["tmux", "has-session", "-t", "Sinon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            ).returncode == 0

            if not session_exists:
                return jsonify({"error": "tmux session 'Sinon' does not exist."}), 400

            subprocess.run(["tmux", "send-keys", "-t", "Sinon", "python bot.py", "C-m"])
            bot_status = "online"

        return jsonify({"message": "Bot is starting."}), 200

    elif action == "shutdown":
        if bot_status == "offline":
            return jsonify({"error": "Bot is not running."}), 400

        bot_status = "shutting down"
        if os_type == "Windows":
            if bot_process and bot_process.poll() is None:
                bot_process.terminate()
                bot_process.wait()
                bot_process = None
            bot_status = "offline"
        elif os_type == "Linux":
            # Send Ctrl+C to the tmux session
            subprocess.run(["tmux", "send-keys", "-t", "Sinon", "C-c"])
            bot_status = "offline"

        return jsonify({"message": "Bot is shutting down."}), 200

    elif action == "restart":
        bot_status = "restarting"
        if os_type == "Windows":
            if bot_process and bot_process.poll() is None:
                bot_process.terminate()
                bot_process.wait()
                bot_process = subprocess.Popen(["python", BOT_SCRIPT], creationflags=subprocess.CREATE_NEW_CONSOLE)
            bot_status = "online"
        elif os_type == "Linux":
            # Restart the bot in the tmux session
            subprocess.run(["tmux", "send-keys", "-t", "Sinon", "C-c"])
            subprocess.run(["tmux", "send-keys", "-t", "Sinon", "python bot.py", "C-m"])
            bot_status = "online"

        return jsonify({"message": "Bot is restarting."}), 200

    return jsonify({"error": "Invalid action."}), 400

def control_bot_start():
    global bot_process
    # Start the bot in a detached process
    if os.name == "nt":  # Windows
        bot_process = subprocess.Popen(
            ["python", BOT_SCRIPT],
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # Open in a new console
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:  # Linux/Unix
        bot_process = subprocess.Popen(
            ["python3", BOT_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,  # Detach from terminal
        )
    return jsonify({"message": "Bot is starting..."}), 200

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    return jsonify({"authenticated": session.get('authenticated', False)})

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

@app.after_request
def remove_security_headers(response):
    return response

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