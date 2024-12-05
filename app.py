from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

# Define the path to your Data folder
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'Data')

# Load data from JSON files
def load_json(file_name):
    file_path = os.path.join(DATA_FOLDER, file_name)
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return json.load(file)
    return {}

@app.route('/')
def home():
    # Load data to pass to the HTML template
    channel_settings = load_json('channel_settings.json')
    role_permissions = load_json('role_permission.json')
    targets = load_json('targets.json')
    
    return render_template('index.html', 
                           channel_settings=channel_settings, 
                           role_permissions=role_permissions, 
                           targets=targets)

# API route to fetch data (optional for AJAX requests)
@app.route('/api/stats')
def api_stats():
    data = {
        "channel_settings": load_json('channel_settings.json'),
        "role_permissions": load_json('role_permission.json'),
        "targets": load_json('targets.json')
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)  # Set to False for production