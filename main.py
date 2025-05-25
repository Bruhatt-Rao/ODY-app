import os
import time
import json
from datetime import datetime
from typing import Optional, List, Dict
import git
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
import typer
import requests

# Initialize Typer app
app = typer.Typer()

# Initialize Rich console
console = Console()

# API configuration
API_BASE_URL = "https://659b-204-88-157-148.ngrok-free.app"

# Store the last known commit hash to detect changes
last_known_commit = None

# Achievement definitions
ACHIEVEMENTS = {
    'first_commit': {
        'name': 'First Commit',
        'description': 'Make your first commit',
        'points': 100
    },
    'commit_master': {
        'name': 'Commit Master',
        'description': 'Make 10 commits',
        'points': 500
    },
    'commit_enthusiast': {
        'name': 'Commit Enthusiast',
        'description': 'Make 5 commits in a single day',
        'points': 300
    },
    'commit_streak': {
        'name': 'Commit Streak',
        'description': 'Make commits for 3 consecutive days',
        'points': 400
    },
    'message_pro': {
        'name': 'Message Pro',
        'description': 'Write a commit message longer than 100 characters',
        'points': 200
    },
    'multi_file': {
        'name': 'Multi-file Master',
        'description': 'Modify 3 or more files in a single commit',
        'points': 250
    },
    'early_bird': {
        'name': 'Early Bird',
        'description': 'Make a commit before 9 AM',
        'points': 150
    },
    'night_owl': {
        'name': 'Night Owl',
        'description': 'Make a commit after 9 PM',
        'points': 150
    }
}

def get_username() -> str:
    """Get username from user input."""
    while True:
        username = console.input("[bold blue]Enter your username: [/bold blue]").strip()
        if username:
            return username
        console.print("[red]Username cannot be empty. Please try again.[/red]")

def load_user_data(username: str) -> dict:
    """Load user data from the API."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/user/{username}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error getting user data: {e}[/red]")
        return None

def save_user_data(username: str, data: dict) -> bool:
    """Save user data to the API."""
    try:
        response = requests.post(f"{API_BASE_URL}/api/user/{username}", json=data)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error saving user data: {e}[/red]")
        return False

def get_git_repo() -> Optional[git.Repo]:
    """Get the Git repository for the current directory."""
    try:
        return git.Repo('.')
    except git.InvalidGitRepositoryError:
        console.print("[red]Error: Not a git repository. Please initialize git first.[/red]")
        return None

def calculate_commit_points(commit: git.Commit) -> int:
    """Calculate points for a commit based on various factors."""
    points = 50  # Base points for any commit
    
    # Points for commit message length (encourage good commit messages)
    message_length = len(commit.message)
    points += min(message_length // 10, 50)  # Up to 50 points for message length
    
    # Points for number of files changed
    files_changed = len(commit.stats.files)
    points += files_changed * 5
    
    # Bonus points for early morning or late night commits
    commit_hour = commit.committed_datetime.hour
    if commit_hour < 9:  # Early bird
        points += 20
    elif commit_hour >= 21:  # Night owl
        points += 20
    
    return points

def update_progress(username: str):
    """Update user progress based on git activity."""
    repo = get_git_repo()
    if not repo:
        return
    
    data = load_user_data(username)
    if not data:
        console.print(f"[red]Error: Could not load data for user {username}[/red]")
        return
    
    progress = data['user_progress']
    
    # Get all commits
    all_commits = list(repo.iter_commits())
    
    # Find new commits since last update
    if progress['last_processed_commit']:
        try:
            last_commit_index = next(i for i, c in enumerate(all_commits) 
                                   if c.hexsha == progress['last_processed_commit'])
            new_commits = all_commits[:last_commit_index]
        except StopIteration:
            new_commits = all_commits
    else:
        new_commits = all_commits
    
    if not new_commits:
        return
    
    # Update the last processed commit
    progress['last_processed_commit'] = new_commits[0].hexsha
    
    # Update commit count
    progress['commits_count'] = len(all_commits)
    
    # Calculate points only for new commits
    new_points = 0
    for commit in new_commits:
        new_points += calculate_commit_points(commit)
    
    progress['total_points'] += new_points
    progress['last_updated'] = datetime.now().isoformat()
    
    # Track commit times for streak and time-based achievements
    commit_times = [c.committed_datetime for c in all_commits]
    commit_dates = set(c.date() for c in commit_times)
    
    # Check achievements
    unlocked_achievements = {a['name'] for a in data['achievements'] if a.get('unlocked_at')}
    
    for achievement_id, achievement_data in ACHIEVEMENTS.items():
        if achievement_data['name'] in unlocked_achievements:
            continue
            
        achievement = next((a for a in data['achievements'] if a['name'] == achievement_data['name']), None)
        if not achievement:
            achievement = {
                'name': achievement_data['name'],
                'description': achievement_data['description'],
                'points': achievement_data['points'],
                'unlocked_at': None
            }
            data['achievements'].append(achievement)
        
        # Check if achievement should be unlocked
        if not achievement['unlocked_at']:
            if achievement_id == 'first_commit' and progress['commits_count'] >= 1:
                achievement['unlocked_at'] = datetime.now().isoformat()
                progress['total_points'] += achievement['points']
            elif achievement_id == 'commit_master' and progress['commits_count'] >= 10:
                achievement['unlocked_at'] = datetime.now().isoformat()
                progress['total_points'] += achievement['points']
            elif achievement_id == 'commit_enthusiast':
                # Check for 5 commits in a single day
                commits_per_day = {}
                for commit_time in commit_times:
                    day = commit_time.date()
                    commits_per_day[day] = commits_per_day.get(day, 0) + 1
                if any(count >= 5 for count in commits_per_day.values()):
                    achievement['unlocked_at'] = datetime.now().isoformat()
                    progress['total_points'] += achievement['points']
            elif achievement_id == 'commit_streak':
                # Check for 3 consecutive days of commits
                sorted_dates = sorted(commit_dates)
                for i in range(len(sorted_dates) - 2):
                    if (sorted_dates[i+1] - sorted_dates[i]).days == 1 and \
                       (sorted_dates[i+2] - sorted_dates[i+1]).days == 1:
                        achievement['unlocked_at'] = datetime.now().isoformat()
                        progress['total_points'] += achievement['points']
                        break
            elif achievement_id == 'message_pro':
                # Check for long commit message
                if any(len(c.message) > 100 for c in all_commits):
                    achievement['unlocked_at'] = datetime.now().isoformat()
                    progress['total_points'] += achievement['points']
            elif achievement_id == 'multi_file':
                # Check for multi-file commit
                if any(len(c.stats.files) >= 3 for c in all_commits):
                    achievement['unlocked_at'] = datetime.now().isoformat()
                    progress['total_points'] += achievement['points']
            elif achievement_id == 'early_bird':
                # Check for early morning commit
                if any(c.committed_datetime.hour < 9 for c in all_commits):
                    achievement['unlocked_at'] = datetime.now().isoformat()
                    progress['total_points'] += achievement['points']
            elif achievement_id == 'night_owl':
                # Check for late night commit
                if any(c.committed_datetime.hour >= 21 for c in all_commits):
                    achievement['unlocked_at'] = datetime.now().isoformat()
                    progress['total_points'] += achievement['points']
    
    if not save_user_data(username, data):
        console.print(f"[red]Error: Could not save data for user {username}[/red]")

def display_progress(username: str):
    """Display user progress and achievements."""
    clear_terminal()
    
    data = load_user_data(username)
    if not data:
        console.print(f"[red]Error: Could not load data for user {username}[/red]")
        return
    
    progress = data['user_progress']
    achievements = data['achievements']
    
    if not progress:
        console.print("[yellow]No progress recorded yet. Make some commits to get started![/yellow]")
        return
    
    # Get current and next rank
    current_rank = data['current_rank']
    next_rank = data['next_rank']
    
    # Calculate progress to next rank
    rank_progress = 0
    if next_rank:
        points_for_current = current_rank['points_required']
        points_for_next = next_rank['points_required']
        points_in_rank = points_for_next - points_for_current
        points_earned = progress['total_points'] - points_for_current
        rank_progress = (points_earned / points_in_rank) * 100 if points_in_rank > 0 else 100
    
    # Display progress
    console.print(Panel.fit(
        f"[bold green]Total Points: {progress['total_points']}[/bold green]\n"
        f"Current Rank: {current_rank['emoji']} {current_rank['name']}\n"
        f"Commits: {progress['commits_count']}\n"
        f"Last Updated: {progress['last_updated']}",
        title="Your Progress"
    ))
    
    # Display rank progress if there's a next rank
    if next_rank:
        console.print(Panel.fit(
            f"Progress to {next_rank['emoji']} {next_rank['name']}: {rank_progress:.1f}%\n"
            f"Points needed: {next_rank['points_required'] - progress['total_points']}",
            title="Next Rank"
        ))
    
    # Display achievements
    table = Table(title="Achievements")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="magenta")
    table.add_column("Points", style="green")
    table.add_column("Status", style="yellow")
    
    for achievement in achievements:
        status = "✅ Unlocked" if achievement.get('unlocked_at') else "🔒 Locked"
        table.add_row(
            achievement['name'],
            achievement['description'],
            str(achievement['points']),
            status
        )
    
    console.print(table)

def clear_terminal():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_latest_commit_hash() -> Optional[str]:
    """Get the hash of the latest commit."""
    repo = get_git_repo()
    if not repo:
        return None
    try:
        return repo.head.commit.hexsha
    except Exception:
        return None

def check_for_new_commits(username: str) -> bool:
    """Check for new commits and update if found."""
    global last_known_commit
    
    current_commit = get_latest_commit_hash()
    if not current_commit:
        return False
    
    # If this is the first check, just store the commit hash
    if last_known_commit is None:
        last_known_commit = current_commit
        return False
    
    # If the commit hash has changed, update the progress
    if current_commit != last_known_commit:
        last_known_commit = current_commit
        update_progress(username)
        return True
    
    return False

@app.command()
def start():
    """Start tracking git activity."""
    clear_terminal()
    console.print("[bold green]Welcome to Code Game! 🎮[/bold green]")
    
    # Check if API is available
    try:
        response = requests.get(f"{API_BASE_URL}/api/users")
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error: Could not connect to API server: {e}[/red]")
        console.print("[red]Please make sure the API server is running at https://659b-204-88-157-148.ngrok-free.app[/red]")
        return
    
    # Get username
    username = get_username()
    
    # Check if user exists in API
    data = load_user_data(username)
    if not data:
        console.print(f"[yellow]First time user detected! Creating profile for {username}...[/yellow]")
        # Create initial data
        initial_data = {
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
        if not save_user_data(username, initial_data):
            console.print("[red]Error: Could not create user profile. Please try again.[/red]")
            return
        console.print(f"[green]Welcome, {username}! Your profile has been created.[/green]")
    else:
        console.print(f"[green]Welcome back, {username}![/green]")
    
    console.print("Tracking your coding progress...")
    
    # Display initial progress
    display_progress(username)
    
    try:
        while True:
            if check_for_new_commits(username):
                display_progress(username)
            time.sleep(1)  # Check every second
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping git activity tracking...[/yellow]")

@app.command()
def status():
    """Show current progress and achievements."""
    username = get_username()
    display_progress(username)

if __name__ == "__main__":
    app() 