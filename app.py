from extensions import socketio
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, abort
from flask_socketio import SocketIO, emit
import os
import json
import threading
import time
import signal
import psutil
from datetime import datetime
from modules.orchestrator import NovaClipOrchestrator
import traceback
import threading
from threading import Thread


app = Flask(__name__)
app.config['SECRET_KEY'] = 'nova-clip-secret-key-2025'
socketio.init_app(app, 
                 cors_allowed_origins="*",
                 logger=True,
                 engineio_logger=True,
                 async_mode='threading')



# Global orchestrator instance
active_connections = set()
orchestrator = None
processing_thread = None
stop_processing = False
current_session_data = {}

def load_users():
    """Load users from users.json file"""
    # Construct the path relative to this file's location
    current_dir = os.path.dirname(os.path.abspath(__file__))
    users_path = os.path.join(current_dir, 'auth', 'users.json')
    
    try:
        with open(users_path, 'r') as f:
            data = json.load(f)
            return {user['username']: user for user in data['users']}
    except FileNotFoundError:
        # Create default users file if it doesn't exist
        default_users = {
            "users": [
                {
                    "username": "admin",
                    "password": "nova2025",
                    "role": "administrator"
                }
            ]
        }
        # Ensure the auth directory exists
        os.makedirs(os.path.dirname(users_path), exist_ok=True)
        with open(users_path, 'w') as f:
            json.dump(default_users, f, indent=2)
        return {"admin": {"username": "admin", "password": "nova2025", "role": "administrator"}}
    except Exception as e:
        print(f"Error loading users: {e}")
        return {}

def get_latest_trends_file():
    """Get the most recent trends file"""
    trends_dir = 'outputs/trends_data'
    if not os.path.exists(trends_dir):
        return None
    
    files = [f for f in os.listdir(trends_dir) if f.endswith('.xlsx')]
    if not files:
        return None
    
    # Sort by modification time, newest first
    files.sort(key=lambda x: os.path.getmtime(os.path.join(trends_dir, x)), reverse=True)
    return os.path.join(trends_dir, files[0])

def safe_cleanup_processes():
    """Safely cleanup only ChromeDriver processes without affecting browser"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Skip if we can't access process info
                if not proc.info['name']:
                    continue
                    
                # Target only ChromeDriver processes
                if 'chromedriver' in proc.info['name'].lower():
                    print(f"Terminating ChromeDriver: {proc.info}")
                    proc.terminate()
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        print(f"Error in process cleanup: {e}")

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Load users from file
        users = load_users()
        
        if username in users and users[username]['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = users[username].get('role', 'user')
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/logout')
def logout():
    global stop_processing
    # Stop any running process when user logs out
    stop_processing = True
    if orchestrator:
        orchestrator.stop_processing = True
    
    # Clean up session
    session.clear()
    return redirect(url_for('login'))

@app.route('/start_process', methods=['POST'])
def start_process():
    global orchestrator, processing_thread, stop_processing, current_session_data
    
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Check if already processing
    if processing_thread and processing_thread.is_alive():
        return jsonify({'error': 'Process already running'}), 400
    
    data = request.get_json()
    geo_region = data.get('geo_region', 'US')
    source_url = data.get('source_url', f'https://trends.google.com/tv/?rows=5&cols=5&geo={geo_region}')
    
    # Reset stop flag
    stop_processing = False
    
    # Initialize session data
    current_session_data = {
        'start_time': datetime.now().isoformat(),
        'geo_region': geo_region,
        'source_url': source_url,
        'status': 'starting'
    }
    
    # Create orchestrator
    orchestrator = NovaClipOrchestrator(socketio, geo_region, source_url)
    
    # Start processing in a separate thread
    processing_thread = threading.Thread(
        target=run_processing_pipeline,
        daemon=True,
        name='ProcessingPipeline'
    )
    processing_thread.start()
    
    # Verify thread started
    if processing_thread.is_alive():
        current_session_data['status'] = 'running'
        return jsonify({
            'status': 'started',
            'message': 'Processing started successfully',
            'thread': processing_thread.name
        })
    else:
        return jsonify({
            'error': 'Failed to start processing thread'
        }), 500

@app.route('/stop_process', methods=['POST'])
def stop_process():
    global stop_processing, orchestrator
    
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        print("=== STOP REQUEST RECEIVED ===")
        stop_processing = True
        
        # Signal orchestrator to stop
        if orchestrator:
            print("Signaling orchestrator to stop...")
            orchestrator.stop_processing = True
            
            # Safely close any active drivers
            if hasattr(orchestrator, 'scraper') and hasattr(orchestrator.scraper, 'driver') and orchestrator.scraper.driver:
                try:
                    print("Closing browser driver...")
                    orchestrator.scraper.driver.quit()
                    orchestrator.scraper.driver = None
                except Exception as e:
                    print(f"Error closing driver: {e}")
        
        # Clean up ChromeDriver processes
        safe_cleanup_processes()
        
        # Emit stop signal to frontend
        socketio.emit('process_stopped', {
            'message': 'Processing stopped by user request'
        })
        
        # Send success response
        return jsonify({
            'status': 'stopped',
            'message': 'Processing stopped successfully'
        })
        
    except Exception as e:
        print(f"Error in stop_process: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def run_processing_pipeline():
    """Run the processing pipeline with stop checks and proper broadcasting"""
    global orchestrator, stop_processing, current_session_data
    
    print("\n=== PIPELINE STARTED ===")
    
    try:
        def emit_to_all(event, data):
            """Helper to emit to all connected clients"""
            print(f"Broadcasting {event}: {data}")
            # Use room parameter instead of broadcast for compatibility
            socketio.emit(event, data, room=None)
            # Add timestamp and debug info
            data['timestamp'] = datetime.now().isoformat()
            data['debug'] = {'thread': threading.current_thread().name}
            socketio.emit(event, data, namespace='/', callback=lambda: print(f"Confirmed {event} received by client"))

        if stop_processing:
            emit_to_all('log', {'message': 'Process stopped before starting', 'type': 'warning'})
            emit_to_all('stage_update', {'stage': 1, 'status': 'error', 'details': 'Stopped by user'})
            return
            
        # Stage 1: Scraping
        #emit_to_all('stage_update', {'stage': 1, 'status': 'processing', 'details': 'Starting scraping process'})
        emit_to_all('log', {'message': '🏁 Stage 1: Scraping [Started]', 'type': 'info'})
        emit_to_all('progress', {'percentage': 10})
        emit_to_all('stage_update', {
            'stage': 1, 
            'status': 'processing', 
            'details': 'Starting scraping process',
            'debug_info': 'Initial stage update'
        })
        
        stage1_output = orchestrator.run_stage_one()
        
        if stop_processing:
            emit_to_all('log', {'message': '⛔ Stage 1 stopped by user', 'type': 'warning'})
            emit_to_all('stage_update', {'stage': 1, 'status': 'error', 'details': 'Stopped by user'})
            return
            
        if not stage1_output:
            emit_to_all('process_error', {'error': 'Stage 1 failed to produce output'})
            emit_to_all('stage_update', {'stage': 1, 'status': 'error', 'details': 'No output file generated'})
            emit_to_all('log', {'message': '❌ Stage 1 failed - no output file', 'type': 'error'})
            return
        
        # Get record counts for Stage 1
        try:
            import pandas as pd
            df = pd.read_excel(stage1_output)
            total_records = len(df)
            verified_records = len(df[df.get('GPT Verified', False) == True])
            current_session_data['stage1_records'] = total_records
            current_session_data['stage1_verified'] = verified_records
            
            emit_to_all('stage_update', {
                'stage': 1, 
                'status': 'completed',
                'details': f'Completed - {verified_records} verified records from {total_records} total'
            })
            emit_to_all('log', {
                'message': f'📊 Stage 1: Found {total_records} records ({verified_records} verified)',
                'type': 'success'
            })
        except Exception as e:
            emit_to_all('stage_update', {
                'stage': 1, 
                'status': 'completed',
                'details': 'Completed (unable to verify record count)'
            })
            emit_to_all('log', {
                'message': f'⚠️ Could not verify record counts: {str(e)}',
                'type': 'warning'
            })
        
        emit_to_all('progress', {'percentage': 33})
        time.sleep(1)  # Brief pause between stages
        
        if stop_processing:
            emit_to_all('log', {'message': '⛔ Processing stopped between stages', 'type': 'warning'})
            emit_to_all('stage_update', {'stage': 2, 'status': 'error', 'details': 'Stopped by user'})
            return
        
        # Stage 2: Script Generation
        emit_to_all('stage_update', {'stage': 2, 'status': 'processing', 'details': 'Starting script generation'})
        emit_to_all('log', {'message': '🎬 Stage 2: Script Generation [Started]', 'type': 'info'})
        emit_to_all('progress', {'percentage': 40})
        
        stage2_success = orchestrator.run_stage_two(stage1_output)
        
        if not stage2_success:
            if not stop_processing:
                emit_to_all('process_error', {'error': 'Stage 2 script generation failed'})
                emit_to_all('stage_update', {
                    'stage': 2, 
                    'status': 'error',
                    'details': 'Script generation failed'
                })
                emit_to_all('log', {'message': '❌ Stage 2: Script generation failed', 'type': 'error'})
            else:
                emit_to_all('log', {'message': '⛔ Stage 2 stopped by user', 'type': 'warning'})
                emit_to_all('stage_update', {
                    'stage': 2, 
                    'status': 'error',
                    'details': 'Stopped by user'
                })
            return
        
        if stop_processing:
            emit_to_all('log', {'message': '⛔ Processing stopped during stage 2', 'type': 'warning'})
            emit_to_all('stage_update', {'stage': 2, 'status': 'error', 'details': 'Stopped by user'})
            return
            
        # Get script count
        try:
            scripts_dir = 'outputs/scripts'
            script_count = len([f for f in os.listdir(scripts_dir) if f.endswith('.txt')])
            current_session_data['stage2_success'] = script_count
            
            emit_to_all('stage_update', {
                'stage': 2, 
                'status': 'completed',
                'details': f'Generated {script_count} scripts'
            })
            emit_to_all('log', {
                'message': f'📝 Stage 2: Generated {script_count} scripts',
                'type': 'success'
            })
        except Exception as e:
            emit_to_all('stage_update', {'stage': 2, 'status': 'completed'})
            emit_to_all('log', {
                'message': f'⚠️ Could not verify script count: {str(e)}',
                'type': 'warning'
            })
        
        emit_to_all('progress', {'percentage': 66})
        time.sleep(1)  # Brief pause between stages
        
        if stop_processing:
            emit_to_all('log', {'message': '⛔ Processing stopped between stages', 'type': 'warning'})
            emit_to_all('stage_update', {'stage': 3, 'status': 'error', 'details': 'Stopped by user'})
            return
        
        # Stage 3: Image Generation
        emit_to_all('stage_update', {
            'stage': 3, 
            'status': 'processing',
            'details': 'Starting image generation'
        })
        emit_to_all('log', {'message': '🖼️ Stage 3: Image Generation [Started]', 'type': 'info'})
        emit_to_all('progress', {'percentage': 70})
        
        stage3_success = orchestrator.run_stage_three(stage1_output)
        
        if not stage3_success:
            if not stop_processing:
                emit_to_all('process_error', {'error': 'Stage 3 image generation failed'})
                emit_to_all('stage_update', {
                    'stage': 3, 
                    'status': 'error',
                    'details': 'Image generation failed'
                })
                emit_to_all('log', {'message': '❌ Stage 3: Image generation failed', 'type': 'error'})
            else:
                emit_to_all('log', {'message': '⛔ Stage 3 stopped by user', 'type': 'warning'})
                emit_to_all('stage_update', {
                    'stage': 3, 
                    'status': 'error',
                    'details': 'Stopped by user'
                })
            return
        
        if stop_processing:
            emit_to_all('log', {'message': '⛔ Processing stopped during stage 3', 'type': 'warning'})
            emit_to_all('stage_update', {'stage': 3, 'status': 'error', 'details': 'Stopped by user'})
            return
            
        # Get image count
        try:
            images_dir = 'outputs/images'
            image_count = sum([len(files) for _, _, files in os.walk(images_dir)])
            current_session_data['stage3_success'] = image_count
            
            emit_to_all('stage_update', {
                'stage': 3, 
                'status': 'completed',
                'details': f'Generated {image_count} images'
            })
            emit_to_all('log', {
                'message': f'🖼️ Stage 3: Generated {image_count} images',
                'type': 'success'
            })
        except Exception as e:
            emit_to_all('stage_update', {'stage': 3, 'status': 'completed'})
            emit_to_all('log', {
                'message': f'⚠️ Could not verify image count: {str(e)}',
                'type': 'warning'
            })
        
        emit_to_all('progress', {'percentage': 100})
        
        # Success!
        if not stop_processing:
            emit_to_all('process_complete', {
                'message': 'All stages completed successfully',
                'trends_file': os.path.basename(stage1_output),
                'stats': {
                    'records': current_session_data.get('stage1_records', 0),
                    'scripts': current_session_data.get('stage2_success', 0),
                    'images': current_session_data.get('stage3_success', 0)
                }
            })
            emit_to_all('log', {'message': '🎉 All stages completed successfully!', 'type': 'success'})

    except Exception as e:
        print(f"\n!!! PIPELINE ERROR: {str(e)}\n")
        traceback.print_exc()
        if not stop_processing:
            error_msg = f'Pipeline failed: {str(e)}'
            print(error_msg)
            socketio.emit('process_error', {'error': error_msg})
            socketio.emit('log', {'message': f'❌ Process failed: {str(e)}', 'type': 'error'})
        else:
            socketio.emit('log', {'message': 'Process stopped by user', 'type': 'warning'})
    finally:
        print("\n=== PIPELINE FINISHED ===\n")

@app.route('/get_results')
def get_results():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Get results organized by date
    results_data = {
        'runs': []
    }
    
    try:
        # Check for trends data and organize by date
        trends_dir = 'outputs/trends_data'
        scripts_dir = 'outputs/scripts'
        images_dir = 'outputs/images'
        
        if os.path.exists(trends_dir):
            trends_files = [f for f in os.listdir(trends_dir) if f.endswith('.xlsx')]
            
            # Group files by date
            runs_by_date = {}
            
            for file in trends_files:
                file_path = os.path.join(trends_dir, file)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                date_key = file_time.strftime('%Y-%m-%d')
                
                if date_key not in runs_by_date:
                    runs_by_date[date_key] = {
                        'date': date_key,
                        'timestamp': file_time,
                        'trends_files': [],
                        'script_files': [],
                        'image_folders': []
                    }
                
                runs_by_date[date_key]['trends_files'].append(file)
            
            # Add scripts and images for each date
            if os.path.exists(scripts_dir):
                script_files = [f for f in os.listdir(scripts_dir) if f.endswith('.txt')]
                for file in script_files:
                    file_path = os.path.join(scripts_dir, file)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    date_key = file_time.strftime('%Y-%m-%d')
                    
                    if date_key in runs_by_date:
                        runs_by_date[date_key]['script_files'].append(file)
            
            if os.path.exists(images_dir):
                image_folders = [d for d in os.listdir(images_dir) if os.path.isdir(os.path.join(images_dir, d))]
                for folder in image_folders:
                    folder_path = os.path.join(images_dir, folder)
                    folder_time = datetime.fromtimestamp(os.path.getmtime(folder_path))
                    date_key = folder_time.strftime('%Y-%m-%d')
                    
                    if date_key in runs_by_date:
                        runs_by_date[date_key]['image_folders'].append(folder)
            
            # Sort by date (newest first)
            results_data['runs'] = sorted(runs_by_date.values(), 
                                        key=lambda x: x['timestamp'], reverse=True)
    
    except Exception as e:
        print(f"Error getting results: {e}")
    
    return render_template('results.html', results=results_data)

@app.route('/download/<file_type>/<filename>')
def download_file(file_type, filename):
    """Download files from the outputs directory"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Security check - only allow specific file types and sanitize filename
    allowed_types = ['trends_data', 'scripts']
    if file_type not in allowed_types:
        abort(404)
    
    # Sanitize filename to prevent directory traversal
    filename = os.path.basename(filename)
    
    # Determine file path based on type
    if file_type == 'trends_data':
        file_path = os.path.join('outputs/trends_data', filename)
        if not filename.endswith('.xlsx'):
            abort(404)
    elif file_type == 'scripts':
        file_path = os.path.join('outputs/scripts', filename)
        if not filename.endswith('.txt'):
            abort(404)
    
    # Check if file exists
    if not os.path.exists(file_path):
        abort(404)
    
    try:
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"Error downloading file: {e}")
        abort(500)

@app.route('/browse_images/<folder_name>')
def browse_images(folder_name):
    """Browse images in a specific folder"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Sanitize folder name
    folder_name = os.path.basename(folder_name)
    folder_path = os.path.join('outputs/images', folder_name)
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        abort(404)
    
    # Get list of image files
    image_files = []
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    try:
        for filename in os.listdir(folder_path):
            if any(filename.lower().endswith(ext) for ext in allowed_extensions):
                image_files.append(filename)
        
        image_files.sort()  # Sort alphabetically
        
        return render_template('browse_images.html', 
                             folder_name=folder_name, 
                             image_files=image_files)
    except Exception as e:
        print(f"Error browsing images: {e}")
        abort(500)

@app.route('/view_image/<folder_name>/<filename>')
def view_image(folder_name, filename):
    """Serve individual image files"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Sanitize paths
    folder_name = os.path.basename(folder_name)
    filename = os.path.basename(filename)
    
    file_path = os.path.join('outputs/images', folder_name, filename)
    
    if not os.path.exists(file_path):
        abort(404)
    
    # Check if it's an image file
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        abort(404)
    
    try:
        return send_file(file_path)
    except Exception as e:
        print(f"Error serving image: {e}")
        abort(500)

@app.route('/get_session_data')
def get_session_data():
    """Get current session processing data"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify(current_session_data)

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    active_connections.add(request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    if request.sid in active_connections:
        active_connections.remove(request.sid)

@socketio.on('ping')
def handle_ping():
    emit('pong')
    
@app.route('/threads')
def list_threads():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    threads = []
    for thread in threading.enumerate():
        threads.append({
            'name': thread.name,
            'ident': thread.ident,
            'alive': thread.is_alive()
        })
    return jsonify({'threads': threads})

if __name__ == '__main__':
    # Create output directories
    os.makedirs('outputs/trends_data', exist_ok=True)
    os.makedirs('outputs/scripts', exist_ok=True)
    os.makedirs('outputs/images', exist_ok=True)
    
    # For HTTPS support, you can use SSL context
    # Uncomment the lines below and provide your SSL certificate files
    # import ssl
    # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    # context.load_cert_chain('path/to/cert.pem', 'path/to/key.pem')
    # socketio.run(app, debug=False, host='0.0.0.0', port=5001, ssl_context=context)
    
    # For development, run without SSL
    print(f"Running with async mode: {socketio.async_mode}")
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)