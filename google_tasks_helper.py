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
SCOPES = [
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar.readonly',
]

def authenticate(api='tasks', version='v1'):
    """
    Authenticates with Google APIs using OAuth 2.0
    Returns a service object for the specified API
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

    return build(api, version, credentials=creds)

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
    return estimate_difficulty_and_minutes(task)[0]

def estimate_difficulty_and_minutes(task):
    """
    (difficulty, minutes) for a task, cached in the local store by task id + title
    so each task is only sent to the AI once (and again only if its title changes)
    """
    import store

    task_id = task.get('id', '')
    title = task.get('title', '')
    notes = task.get('notes', '')

    try:
        store.init()
        cached = store.cached_difficulty(task_id, title)
        if cached:
            return cached
    except Exception as e:
        print(f"Warning: difficulty cache unavailable ({e})")

    difficulty, minutes = estimate_task_difficulty_ai(title, notes)

    if task_id:
        try:
            import ai_difficulty_estimator
            store.upsert_task_meta(task_id, title=title, difficulty=difficulty, minutes=minutes,
                                   ai_scored=int(ai_difficulty_estimator.last_was_ai))
        except Exception as e:
            print(f"Warning: could not cache difficulty ({e})")
    return difficulty, minutes

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

def _due_date(task):
    """Google Tasks due dates are date-only (RFC3339 at midnight UTC)"""
    due = task.get('due')
    return due[:10] if due else None

def list_all_tasks():
    """
    Every open task across every task list

    Returns:
        List of dicts: id, list_id, list_title, title, notes, due (YYYY-MM-DD or None),
        parent, position, updated
    """
    service = authenticate()
    out = []
    lists = service.tasklists().list(maxResults=100).execute().get('items', [])
    for tl in lists:
        page_token = None
        while True:
            results = service.tasks().list(
                tasklist=tl['id'], maxResults=100, showCompleted=False,
                showHidden=False, pageToken=page_token
            ).execute()
            for task in results.get('items', []):
                if not task.get('title', '').strip():
                    continue
                out.append({
                    'id': task['id'],
                    'list_id': tl['id'],
                    'list_title': tl.get('title', ''),
                    'title': task.get('title', ''),
                    'notes': task.get('notes', ''),
                    'due': _due_date(task),
                    'parent': task.get('parent'),
                    'position': task.get('position', ''),
                    'updated': task.get('updated', ''),
                })
            page_token = results.get('nextPageToken')
            if not page_token:
                break
    return out

def get_task_lists():
    """[(id, title), ...] in Google's order; the first one is the default list"""
    service = authenticate()
    lists = service.tasklists().list(maxResults=100).execute().get('items', [])
    return [(tl['id'], tl.get('title', '')) for tl in lists]

def create_task(title, tasklist_id=None, notes=None, due=None, parent=None, previous=None):
    """
    Create a task (optionally as a subtask of `parent`, placed after `previous`)

    Args:
        due: 'YYYY-MM-DD' or None

    Returns:
        The created task resource (dict)
    """
    service = authenticate()
    if not tasklist_id:
        tasklist_id = service.tasklists().list(maxResults=1).execute()['items'][0]['id']
    body = {'title': title}
    if notes:
        body['notes'] = notes
    if due:
        body['due'] = f"{due}T00:00:00.000Z"
    kwargs = {}
    if parent:
        kwargs['parent'] = parent
    if previous:
        kwargs['previous'] = previous
    task = service.tasks().insert(tasklist=tasklist_id, body=body, **kwargs).execute()
    task['list_id'] = tasklist_id
    return task

def update_task(task_id, tasklist_id, **fields):
    """Patch title / notes / due ('YYYY-MM-DD' or '' to clear)"""
    service = authenticate()
    body = {}
    for key in ('title', 'notes'):
        if key in fields:
            body[key] = fields[key]
    if 'due' in fields:
        body['due'] = f"{fields['due']}T00:00:00.000Z" if fields['due'] else None
    return service.tasks().patch(tasklist=tasklist_id, task=task_id, body=body).execute()

def delete_task(task_id, tasklist_id):
    service = authenticate()
    service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()

def token_status():
    """
    ('ok', detail) if the saved Google token works (refreshing it if needed),
    otherwise ('error', reason). Never starts an interactive OAuth flow.
    """
    token_path = os.path.join(os.path.dirname(__file__), 'token.pickle')
    if not os.path.exists(token_path):
        return 'error', 'No token saved. Reconnect Google.'
    try:
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
        if not creds.valid:
            if not creds.refresh_token:
                return 'error', 'Token has no refresh token. Reconnect Google.'
            creds.refresh(Request())
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        build('tasks', 'v1', credentials=creds).tasklists().list(maxResults=1).execute()
        return 'ok', 'Connected'
    except Exception as e:
        return 'error', f'{type(e).__name__}: {e}'

# ===== RECONNECT (phone-friendly OAuth) =====
# The OAuth client is a "Desktop app", so Google only redirects to localhost. From a phone
# that page fails to load, but its URL carries the code: the user pastes it back to finish.
REAUTH_REDIRECT = 'http://localhost:8765/'
_pending_flows = {}

def reauth_start():
    """Returns the Google consent URL to open"""
    flow = InstalledAppFlow.from_client_secrets_file(
        os.path.join(os.path.dirname(__file__), 'credentials.json'), SCOPES,
        redirect_uri=REAUTH_REDIRECT)
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    _pending_flows.clear()
    _pending_flows[state] = flow
    return url

def reauth_finish(redirected_url):
    """Exchange the pasted localhost URL for a new token. Returns (ok, message)."""
    from urllib.parse import urlparse, parse_qs
    os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')  # loopback redirect is plain http
    params = parse_qs(urlparse(redirected_url.strip()).query)
    state = (params.get('state') or [''])[0]
    flow = _pending_flows.get(state)
    if not flow:
        return False, 'That link does not match the current reconnect attempt. Start again.'
    if 'error' in params:
        return False, f"Google said: {params['error'][0]}"
    try:
        flow.fetch_token(authorization_response=redirected_url.strip())
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
    with open(os.path.join(os.path.dirname(__file__), 'token.pickle'), 'wb') as token:
        pickle.dump(flow.credentials, token)
    _pending_flows.clear()
    return True, 'Google reconnected.'

def get_calendar_events(max_events=10, days_offset=0):
    """
    Get calendar events from Google Calendar

    Args:
        max_events: Maximum number of events to return
        days_offset: 0 = today, 1 = tomorrow, etc.

    Returns:
        List of tuples: (time_str, title, is_all_day)
    """
    from datetime import datetime as dt, timedelta

    service = authenticate('calendar', 'v3')

    now = dt.now().astimezone()
    target_day = now + timedelta(days=days_offset)
    start_of_day = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_day.replace(hour=23, minute=59, second=59, microsecond=0)

    try:
        results = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            maxResults=max_events
        ).execute()

        events = results.get('items', [])
        parsed = []
        for event in events:
            title = event.get('summary', 'Untitled Event')
            start = event.get('start', {})
            if 'dateTime' in start:
                event_dt = dt.fromisoformat(start['dateTime'])
                parsed.append((event_dt.strftime('%H:%M'), title, False))
            elif 'date' in start:
                parsed.append(('ALL DAY', title, True))

        return parsed
    except Exception as e:
        print(f"Warning: Calendar fetch failed ({e})")
        return []

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
