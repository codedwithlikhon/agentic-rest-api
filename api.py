from flask import Flask, request, jsonify
from datetime import datetime
from functools import wraps
import uuid
import requests
import os

app = Flask(__name__)

# In-memory storage (replace with database in production)
projects_db = {}
chats_db = {}
messages_db = {}
users_db = {}

# Mock authentication
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Missing token'}), 401
        return f(*args, **kwargs)
    return decorated

# Helper functions
def generate_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def get_pagination(page=1, limit=20):
    return {'page': page, 'limit': limit}

def get_user_from_token():
    """Get the user ID from the request token (mock implementation)."""
    token = request.headers.get('Authorization')
    # In a real application, you would decode the JWT to get the user ID.
    # For this example, we'll use a simple mapping.
    # Let's assume the token is 'Bearer <user_id>'
    if token and token.startswith('Bearer '):
        return token.split(' ')[1]
    return None

MINIMAX_API_key = os.environ.get('MINIMAX_API_KEY', '')
MINIMAX_API_URL = 'https://api.minimaxi.chat/v1/text/chatcompletion'

def generate_ai_response(chat_id, conversation_history):
    """Generate AI response using minimax-m2 model"""
    try:
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'minimax-m2',
            'messages': conversation_history,
            'temperature': 0.7,
            'max_tokens': 1024
        }
        
        response = requests.post(MINIMAX_API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0].get('message', {}).get('content', '')
        return None
    except Exception as e:
        app.logger.error(f"Error calling minimax API: {str(e)}")
        return None

def generate_thoughts(chat_id, prompt, goal, total_thoughts):
    """Generate a sequence of thoughts to solve a problem."""
    thoughts = []
    conversation_history = [{'role': 'user', 'content': f"Problem: {prompt}\nGoal: {goal}"}]

    for i in range(total_thoughts):
        # Add previous thoughts to the conversation history for context
        if i > 0:
            last_thought = thoughts[-1]['content']
            conversation_history.append({'role': 'assistant', 'content': last_thought})
            conversation_history.append({'role': 'user', 'content': "What is the next step?"})

        # Generate the next thought
        ai_response = generate_ai_response(chat_id, conversation_history)
        if not ai_response:
            return None, None

        thought = {'id': i + 1, 'content': ai_response}
        thoughts.append(thought)

    # Generate a final answer
    conversation_history.append({'role': 'assistant', 'content': thoughts[-1]['content']})
    conversation_history.append({'role': 'user', 'content': "Based on the previous thoughts, what is the final answer?"})
    final_answer = generate_ai_response(chat_id, conversation_history)

    return thoughts, final_answer

# Projects endpoints
@app.get('/v1/projects')
@token_required
def list_projects():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    projects_list = list(projects_db.values())
    total = len(projects_list)
    
    start = (page - 1) * limit
    end = start + limit
    
    return jsonify({
        'data': projects_list[start:end],
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit
        }
    }), 200

@app.post('/v1/projects')
@token_required
def create_project():
    data = request.get_json()
    
    creator_id = get_user_from_token()
    if not creator_id or creator_id not in users_db:
        return jsonify({'error': 'Invalid or missing user token'}), 401

    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    project_id = generate_id('proj')
    project = {
        'id': project_id,
        'name': data['name'],
        'description': data.get('description', ''),
        'status': 'active',
        'members': [{'user_id': creator_id, 'role': 'owner'}],
        'activity': [],
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'metadata': data.get('metadata', {})
    }
    
    projects_db[project_id] = project
    return jsonify(project), 201

@app.get('/v1/projects/<id>')
@token_required
def get_project(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(project), 200

@app.put('/v1/projects/<id>')
@token_required
def update_project(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    user_id = get_user_from_token()
    if not user_id:
        return jsonify({'error': 'Invalid or missing user token'}), 401

    user_role = ''
    for member in project['members']:
        if member['user_id'] == user_id:
            user_role = member['role']
            break

    if user_role not in ['owner', 'editor']:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json()
    project.update({
        'name': data.get('name', project['name']),
        'description': data.get('description', project['description']),
        'updated_at': datetime.utcnow().isoformat() + 'Z'
    })
    
    record_activity(project, user_id, f"updated project details")

    return jsonify(project), 200

@app.delete('/v1/projects/<id>')
@token_required
def delete_project(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    user_id = get_user_from_token()
    if not user_id:
        return jsonify({'error': 'Invalid or missing user token'}), 401

    user_role = ''
    for member in project['members']:
        if member['user_id'] == user_id:
            user_role = member['role']
            break

    if user_role != 'owner':
        return jsonify({'error': 'Permission denied'}), 403

    if id in projects_db:
        del projects_db[id]
        return '', 204
    return jsonify({'error': 'Project not found'}), 404

@app.patch('/v1/projects/<id>/status')
@token_required
def update_project_status(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    data = request.get_json()
    status = data.get('status')
    
    if status not in ['active', 'archived', 'deleted']:
        return jsonify({'error': 'Invalid status'}), 400
    
    project['status'] = status
    project['updated_at'] = datetime.utcnow().isoformat() + 'Z'
    
    return jsonify(project), 200

@app.get('/v1/projects/<id>/analytics')
@token_required
def get_project_analytics(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    analytics = {
        'project_id': id,
        'views': 245,
        'stars': 19,
        'messages_count': len([m for m in messages_db.values() if m.get('project_id') == id]),
        'last_activity': datetime.utcnow().isoformat() + 'Z'
    }
    
    return jsonify(analytics), 200

# Users endpoints
@app.get('/v1/users')
@token_required
def list_users():
    return jsonify(list(users_db.values())), 200

@app.post('/v1/users')
@token_required
def create_user():
    data = request.get_json()

    if not data.get('name') or not data.get('email'):
        return jsonify({'error': 'Name and email are required'}), 400

    user_id = generate_id('user')
    user = {
        'id': user_id,
        'name': data['name'],
        'email': data['email'],
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }

    users_db[user_id] = user
    return jsonify(user), 201

def record_activity(project, user_id, action):
    """Record an activity in the project's activity log."""
    activity = {
        'id': generate_id('act'),
        'user_id': user_id,
        'action': action,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    project['activity'].append(activity)

# Project Members endpoints
@app.get('/v1/projects/<id>/members')
@token_required
def list_project_members(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify(project['members']), 200

@app.post('/v1/projects/<id>/members')
@token_required
def add_project_member(id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    requesting_user_id = get_user_from_token()
    if not requesting_user_id:
        return jsonify({'error': 'Invalid or missing user token'}), 401

    user_role = ''
    for member in project['members']:
        if member['user_id'] == requesting_user_id:
            user_role = member['role']
            break

    if user_role != 'owner':
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    role = data.get('role')

    if not user_id or not role:
        return jsonify({'error': 'user_id and role are required'}), 400

    if user_id not in users_db:
        return jsonify({'error': 'User not found'}), 404

    if role not in ['editor', 'viewer']:
        return jsonify({'error': 'Invalid role'}), 400

    # Check if the user is already a member
    for member in project['members']:
        if member['user_id'] == user_id:
            return jsonify({'error': 'User is already a member'}), 400

    new_member = {'user_id': user_id, 'role': role}
    project['members'].append(new_member)
    record_activity(project, owner_id, f"added member {user_id} as {role}")

    return jsonify(new_member), 201

@app.put('/v1/projects/<id>/members/<user_id>')
@token_required
def update_project_member(id, user_id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    requesting_user_id = get_user_from_token()
    if not requesting_user_id:
        return jsonify({'error': 'Invalid or missing user token'}), 401

    user_role = ''
    for member in project['members']:
        if member['user_id'] == requesting_user_id:
            user_role = member['role']
            break

    if user_role != 'owner':
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()
    role = data.get('role')

    if not role:
        return jsonify({'error': 'role is required'}), 400

    if role not in ['editor', 'viewer']:
        return jsonify({'error': 'Invalid role'}), 400

    for member in project['members']:
        if member['user_id'] == user_id:
            member['role'] = role
            record_activity(project, owner_id, f"updated member {user_id}'s role to {role}")
            return jsonify(member), 200

    return jsonify({'error': 'Member not found'}), 404

@app.delete('/v1/projects/<id>/members/<user_id>')
@token_required
def remove_project_member(id, user_id):
    project = projects_db.get(id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    requesting_user_id = get_user_from_token()
    if not requesting_user_id:
        return jsonify({'error': 'Invalid or missing user token'}), 401

    user_role = ''
    for member in project['members']:
        if member['user_id'] == requesting_user_id:
            user_role = member['role']
            break

    if user_role != 'owner':
        return jsonify({'error': 'Permission denied'}), 403

    for i, member in enumerate(project['members']):
        if member['user_id'] == user_id:
            if member['role'] == 'owner':
                return jsonify({'error': 'Cannot remove the owner'}), 400
            del project['members'][i]
            record_activity(project, requesting_user_id, f"removed member {user_id}")
            return '', 204

    return jsonify({'error': 'Member not found'}), 404

# Chats endpoints
@app.get('/v1/chats')
@token_required
def list_chats():
    limit = request.args.get('limit', 20, type=int)
    chats_list = list(chats_db.values())[:limit]
    return jsonify({'data': chats_list}), 200

@app.post('/v1/chats')
@token_required
def create_chat():
    data = request.get_json()
    
    if not data.get('project_id') or not data.get('participants'):
        return jsonify({'error': 'project_id and participants are required'}), 400
    
    chat_id = generate_id('chat')
    chat = {
        'id': chat_id,
        'project_id': data['project_id'],
        'participants': data['participants'],
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'metadata': data.get('metadata', {})
    }
    
    chats_db[chat_id] = chat
    return jsonify(chat), 201

@app.get('/v1/chats/<id>')
@token_required
def get_chat(id):
    chat = chats_db.get(id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    return jsonify(chat), 200

@app.delete('/v1/chats/<id>')
@token_required
def delete_chat(id):
    if id in chats_db:
        del chats_db[id]
        return '', 204
    return jsonify({'error': 'Chat not found'}), 404

# Messages endpoints
@app.get('/v1/chats/<id>/messages')
@token_required
def list_messages(id):
    chat = chats_db.get(id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    limit = request.args.get('limit', 50, type=int)
    chat_messages = [m for m in messages_db.values() if m['chat_id'] == id]
    
    return jsonify({
        'data': chat_messages[:limit]
    }), 200

@app.post('/v1/chats/<id>/messages')
@token_required
def send_message(id):
    chat = chats_db.get(id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    data = request.get_json()
    
    if not data.get('sender_id') or not data.get('content'):
        return jsonify({'error': 'sender_id and content are required'}), 400
    
    message_id = generate_id('msg')
    message = {
        'id': message_id,
        'chat_id': id,
        'sender_id': data['sender_id'],
        'content': data['content'],
        'type': data.get('type', 'text'),
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'metadata': data.get('metadata', {})
    }
    
    messages_db[message_id] = message
    return jsonify(message), 201

@app.post('/v1/chats/<id>/ai/reply')
@token_required
def generate_ai_reply(id):
    chat = chats_db.get(id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404
    
    data = request.get_json()
    
    if not data.get('sender_id'):
        return jsonify({'error': 'sender_id is required'}), 400
    
    # Get conversation history
    chat_messages = [m for m in messages_db.values() if m['chat_id'] == id]
    chat_messages.sort(key=lambda x: x['created_at'])
    
    # Format for minimax API
    conversation = [
        {'role': 'user' if m['sender_id'] != 'ai_assistant' else 'assistant', 'content': m['content']}
        for m in chat_messages[-10:]  # Last 10 messages for context
    ]
    
    # Generate AI response
    ai_content = generate_ai_response(id, conversation)
    
    if not ai_content:
        return jsonify({'error': 'Failed to generate AI response'}), 500
    
    # Store AI message
    message_id = generate_id('msg')
    ai_message = {
        'id': message_id,
        'chat_id': id,
        'sender_id': 'ai_assistant',
        'content': ai_content,
        'type': 'text',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'metadata': {'model': 'minimax-m2', 'generated': True}
    }
    
    messages_db[message_id] = ai_message
    return jsonify(ai_message), 201

@app.post('/v1/chats/<id>/ai/think')
@token_required
def sequential_thinking(id):
    chat = chats_db.get(id)
    if not chat:
        return jsonify({'error': 'Chat not found'}), 404

    data = request.get_json()
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400

    goal = data.get('goal', '')
    total_thoughts = data.get('totalThoughts', 5)

    thoughts, final_answer = generate_thoughts(id, prompt, goal, total_thoughts)

    if not thoughts:
        return jsonify({'error': 'Failed to generate thoughts'}), 500

    # Store thoughts in the in-memory database
    for thought in thoughts:
        message_id = generate_id('msg')
        message = {
            'id': message_id,
            'chat_id': id,
            'sender_id': 'ai_assistant',
            'content': f"Thought {thought['id']}: {thought['content']}",
            'type': 'text',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'metadata': {'model': 'minimax-m2', 'generated': True, 'is_thought': True}
        }
        messages_db[message_id] = message

    # Store the final answer
    message_id = generate_id('msg')
    message = {
        'id': message_id,
        'chat_id': id,
        'sender_id': 'ai_assistant',
        'content': final_answer,
        'type': 'text',
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'metadata': {'model': 'minimax-m2', 'generated': True}
    }
    messages_db[message_id] = message

    return jsonify({
        'thoughts': thoughts,
        'final_answer': final_answer
    }), 200

# System endpoints
@app.get('/v1/system/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }), 200

# Root endpoint
@app.get('/')
def root():
    return jsonify({
        'name': 'Agentic REST API',
        'version': '1.0.0',
        'status': 'online',
        'health_check': '/v1/system/health',
        'docs': 'OpenAPI spec available at /openapi.yaml'
    }), 200

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True)
