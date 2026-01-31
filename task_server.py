#!/usr/bin/env python3
"""
Task Completion Server
Flask web server for marking Google Tasks complete via QR code scans
"""

from flask import Flask, render_template_string, request
from google_tasks_helper import complete_task
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HTML templates
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Complete!</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: #000;
            color: #0f0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }
        .container {
            max-width: 400px;
            padding: 20px;
            border: 2px solid #0f0;
            background: #001100;
        }
        h1 {
            font-size: 2em;
            margin: 0 0 20px 0;
            text-transform: uppercase;
        }
        .checkmark {
            font-size: 4em;
            margin: 20px 0;
        }
        .rocket-logo {
            width: 60px;
            height: 60px;
            margin: 20px auto;
            filter: brightness(0) saturate(100%) invert(54%) sepia(95%) saturate(1738%) hue-rotate(75deg) brightness(119%) contrast(119%);
        }
        .task-name {
            font-size: 1.2em;
            margin: 20px 0;
            padding: 10px;
            border: 1px solid #0f0;
            word-wrap: break-word;
        }
        .message {
            margin: 20px 0;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✓ Task Complete</h1>
        <img src="https://fastaf.ca/images/rocket.svg" alt="Rocket" class="rocket-logo">
        <div class="task-name">{{ task_name }}</div>
        <div class="message">THERMAL://SYNC OK</div>
        <div class="message">fastAF industries :: NODE 01</div>
    </div>
</body>
</html>
"""

ERROR_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: #000;
            color: #f00;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }
        .container {
            max-width: 400px;
            padding: 20px;
            border: 2px solid #f00;
            background: #110000;
        }
        h1 {
            font-size: 2em;
            margin: 0 0 20px 0;
            text-transform: uppercase;
        }
        .error-icon {
            font-size: 4em;
            margin: 20px 0;
        }
        .message {
            margin: 20px 0;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠ Error</h1>
        <div class="error-icon">✕</div>
        <div class="message">{{ error_message }}</div>
        <div class="message">THERMAL://SYNC FAILED</div>
    </div>
</body>
</html>
"""

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thermal Task Server</title>
    <style>
        body {
            font-family: 'Courier New', monospace;
            background: #000;
            color: #0f0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }
        .container {
            max-width: 400px;
            padding: 20px;
            border: 2px solid #0f0;
            background: #001100;
        }
        h1 {
            font-size: 2em;
            margin: 0 0 20px 0;
            text-transform: uppercase;
        }
        .rocket-logo {
            width: 80px;
            height: 80px;
            margin: 20px auto;
            filter: brightness(0) saturate(100%) invert(54%) sepia(95%) saturate(1738%) hue-rotate(75deg) brightness(119%) contrast(119%);
        }
        .message {
            margin: 20px 0;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Thermal Task Server</h1>
        <img src="https://fastaf.ca/images/rocket.svg" alt="Rocket" class="rocket-logo">
        <div class="message">fastAF industries :: NODE 01</div>
        <div class="message">SERVER ONLINE</div>
        <div class="message">Scan QR codes from task receipts to mark tasks complete</div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    """Home page"""
    return render_template_string(INDEX_TEMPLATE)

@app.route('/complete/<tasklist_id>/<task_id>')
def complete_task_endpoint(tasklist_id, task_id):
    """
    Mark a task as complete
    URL: /complete/<tasklist_id>/<task_id>
    """
    # Get task name from query parameter (optional)
    task_name = request.args.get('name', 'Task')

    logger.info(f"Completing task: {task_id} from list: {tasklist_id}")

    # Complete the task
    success = complete_task(task_id, tasklist_id)

    if success:
        logger.info(f"✓ Task completed: {task_name}")
        return render_template_string(SUCCESS_TEMPLATE, task_name=task_name)
    else:
        logger.error(f"✗ Failed to complete task: {task_name}")
        return render_template_string(
            ERROR_TEMPLATE,
            error_message="Failed to mark task as complete. Please try again."
        )

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'message': 'Thermal Task Server is running'}

if __name__ == '__main__':
    print("=" * 60)
    print("THERMAL TASK SERVER")
    print("fastAF industries :: NODE 01")
    print("=" * 60)
    print(f"\nServer starting on http://192.168.88.130:5000")
    print("Scan QR codes from task receipts to mark tasks complete\n")

    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=False
    )
