"""
Google Tasks API Helper
Handles authentication and task fetching from Google Tasks
"""

import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from ai_difficulty_estimator import estimate_task_difficulty_ai

# If modifying these scopes, delete the file token.pickle
SCOPES = ['https://www.googleapis.com/auth/tasks']

def authenticate():
    """
    Authenticates with Google Tasks API using OAuth 2.0
    Returns a Google Tasks service object
    """
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), 'token.pickle')
    credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')

    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Starting OAuth flow...")
            print("A browser window will open for you to authorize the app.")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
        print("Authentication successful!")

    return build('tasks', 'v1', credentials=creds)

def get_tasks(service, max_results=10):
    """
    Fetch tasks from the default task list

    Args:
        service: Google Tasks service object
        max_results: Maximum number of tasks to return

    Returns:
        List of tuples: (task_title, difficulty_level)
        difficulty_level is estimated based on task length/complexity
    """
    # Get the default task list
    results = service.tasklists().list(maxResults=1).execute()
    task_lists = results.get('items', [])

    if not task_lists:
        print("No task lists found.")
        return []

    # Use the first (default) task list
    tasklist_id = task_lists[0]['id']

    # Fetch tasks that are not completed
    results = service.tasks().list(
        tasklist=tasklist_id,
        maxResults=max_results,
        showCompleted=False,
        showHidden=False
    ).execute()

    tasks = results.get('items', [])

    if not tasks:
        print("No tasks found.")
        return []

    # Convert to our format with difficulty estimation
    task_list = []
    for task in tasks:
        title = task.get('title', 'Untitled Task')
        # Estimate difficulty based on task title length and notes
        difficulty = estimate_difficulty(task)
        task_list.append((title, difficulty))

    return task_list

def estimate_difficulty(task):
    """
    Estimate task difficulty using AI or fallback heuristics

    Args:
        task: Task object from Google Tasks API

    Returns:
        int: Difficulty level (1-3)
    """
    title = task.get('title', '')
    notes = task.get('notes', '')

    # Use AI to estimate difficulty and time
    difficulty, minutes = estimate_task_difficulty_ai(title, notes)

    # For now, we only return difficulty (minutes could be used later)
    return difficulty

def get_tasks_for_printer(max_results=10):
    """
    Convenience function to get tasks ready for the thermal printer

    Returns:
        List of tuples: (task_title, difficulty_level)
    """
    service = authenticate()
    return get_tasks(service, max_results)

def get_tasks_with_ids(max_results=10):
    """
    Get tasks with their IDs for completion tracking

    Returns:
        List of tuples: (task_id, tasklist_id, task_title, difficulty_level)
    """
    service = authenticate()

    # Get the default task list
    results = service.tasklists().list(maxResults=1).execute()
    task_lists = results.get('items', [])

    if not task_lists:
        return []

    tasklist_id = task_lists[0]['id']

    # Fetch tasks that are not completed
    results = service.tasks().list(
        tasklist=tasklist_id,
        maxResults=max_results,
        showCompleted=False,
        showHidden=False
    ).execute()

    tasks = results.get('items', [])

    if not tasks:
        return []

    # Return tasks with IDs
    task_list = []
    for task in tasks:
        task_id = task.get('id', '')
        title = task.get('title', 'Untitled Task')
        difficulty = estimate_difficulty(task)
        task_list.append((task_id, tasklist_id, title, difficulty))

    return task_list

def complete_task(task_id: str, tasklist_id: str) -> bool:
    """
    Mark a task as complete in Google Tasks

    Args:
        task_id: The Google Tasks task ID
        tasklist_id: The Google Tasks list ID

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        service = authenticate()

        # Mark task as completed by setting status to 'completed'
        task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
        task['status'] = 'completed'

        service.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=task
        ).execute()

        return True
    except Exception as e:
        print(f"Error completing task: {e}")
        return False

if __name__ == "__main__":
    # Test the authentication and task fetching
    print("Testing Google Tasks API connection...")
    tasks = get_tasks_for_printer(max_results=5)

    if tasks:
        print(f"\nFound {len(tasks)} tasks:")
        for title, difficulty in tasks:
            print(f"  [{difficulty}] {title}")
    else:
        print("No tasks found or authentication failed.")
