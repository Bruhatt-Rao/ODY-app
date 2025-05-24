from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
# Configure CORS with specific options
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "https://localhost:3000", "*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Accept", "ngrok-skip-browser-warning"]
    }
})

# Add headers to all responses
@app.after_request
def add_headers(response):
    logger.debug(f"Adding headers to response: {response}")
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Accept,ngrok-skip-browser-warning')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Content-Type', 'application/json')
    return response

# Data storage
DATA_DIR = 'user_data'

def ensure_data_dir():
    """Ensure the data directory exists."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def get_user_file(username: str) -> str:
    """Get the file path for a user's data."""
    return os.path.join(DATA_DIR, f"{username}.json")

def load_user_data(username: str) -> dict:
    """Load data for a specific user."""
    file_path = get_user_file(username)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return {
        'username': username,
        'achievements': [],
        'user_progress': {
            'total_points': 0,
            'commits_count': 0,
            'lines_added': 0,
            'lines_deleted': 0,
            'last_updated': datetime.now().isoformat(),
            'last_processed_commit': None
        }
    }

def save_user_data(username: str, data: dict):
    """Save data for a specific user."""
    ensure_data_dir()
    file_path = get_user_file(username)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

# Rank definitions
RANKS = {
    'cardboard': {
        'name': 'Cardboard',
        'points_required': 0,
        'emoji': '📦'
    },
    'bronze': {
        'name': 'Bronze',
        'points_required': 1000,
        'emoji': '🥉'
    },
    'silver': {
        'name': 'Silver',
        'points_required': 2500,
        'emoji': '🥈'
    },
    'gold': {
        'name': 'Gold',
        'points_required': 5000,
        'emoji': '🥇'
    },
    'platinum': {
        'name': 'Platinum',
        'points_required': 10000,
        'emoji': '💠'
    },
    'diamond': {
        'name': 'Diamond',
        'points_required': 20000,
        'emoji': '💎'
    },
    'champion': {
        'name': 'Champion',
        'points_required': 35000,
        'emoji': '🏆'
    },
    'wizard': {
        'name': 'Wizard',
        'points_required': 50000,
        'emoji': '🧙'
    },
    'mastermind': {
        'name': 'Mastermind',
        'points_required': 75000,
        'emoji': '🧠'
    }
}

def get_current_rank(points: int) -> dict:
    """Get the current rank based on points."""
    current_rank = 'cardboard'
    for rank, data in RANKS.items():
        if points >= data['points_required']:
            current_rank = rank
    return RANKS[current_rank]

def get_next_rank(points: int) -> dict:
    """Get the next rank to achieve."""
    for rank, data in sorted(RANKS.items(), key=lambda x: x[1]['points_required']):
        if data['points_required'] > points:
            return data
    return None

@app.route('/api/user/<username>', methods=['GET'])
def get_user_data(username):
    """Get data for a specific user."""
    logger.debug(f"Received GET request for user: {username}")
    try:
        data = load_user_data(username)
        progress = data['user_progress']
        data['current_rank'] = get_current_rank(progress['total_points'])
        data['next_rank'] = get_next_rank(progress['total_points'])
        logger.debug(f"Returning data: {data}")
        return jsonify(data), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"Error in get_user_data: {str(e)}")
        return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

@app.route('/api/user/<username>', methods=['POST'])
def update_user_data(username):
    """Update data for a specific user."""
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400, {'Content-Type': 'application/json'}
        
        new_data = request.get_json()
        current_data = load_user_data(username)
        
        # Update only the fields that are provided
        if 'user_progress' in new_data:
            current_data['user_progress'].update(new_data['user_progress'])
        
        if 'achievements' in new_data:
            current_data['achievements'] = new_data['achievements']
        
        save_user_data(username, current_data)
        return jsonify({'message': 'Data updated successfully', 'data': current_data}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

@app.route('/api/users', methods=['GET'])
def list_users():
    """List all users."""
    logger.debug("Received request to list users")
    try:
        ensure_data_dir()
        users = []
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.json'):
                username = filename[:-5]  # Remove .json extension
                data = load_user_data(username)
                users.append({
                    'username': username,
                    'total_points': data['user_progress']['total_points'],
                    'current_rank': get_current_rank(data['user_progress']['total_points'])['name']
                })
        logger.debug(f"Returning users: {users}")
        return jsonify(users), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"Error in list_users: {str(e)}")
        return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

@app.route('/api/user/<username>/exists', methods=['GET'])
def check_user_exists(username):
    """Check if a user exists."""
    logger.debug(f"Checking if user exists: {username}")
    try:
        file_path = get_user_file(username)
        exists = os.path.exists(file_path)
        logger.debug(f"User {username} exists: {exists}")
        return jsonify({'exists': exists}), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

def run_web_server():
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=4000, debug=True)

if __name__ == '__main__':
    run_web_server() 