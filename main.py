import os
import time
from datetime import datetime
from typing import Optional, List, Dict
import git
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
import typer
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# Initialize Typer app
app = typer.Typer()

# Initialize Rich console
console = Console()

# Database setup
Base = declarative_base()
engine = create_engine('sqlite:///code_game.db')
Session = sessionmaker(bind=engine)

class Achievement(Base):
    __tablename__ = 'achievements'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    points = Column(Integer)
    unlocked_at = Column(DateTime, nullable=True)

class UserProgress(Base):
    __tablename__ = 'user_progress'
    
    id = Column(Integer, primary_key=True)
    total_points = Column(Integer, default=0, nullable=False)
    commits_count = Column(Integer, default=0, nullable=False)
    lines_added = Column(Integer, default=0, nullable=False)
    lines_deleted = Column(Integer, default=0, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, nullable=False)
    last_processed_commit = Column(String, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.total_points = 0
        self.commits_count = 0
        self.lines_added = 0
        self.lines_deleted = 0
        self.last_updated = datetime.now()

# Create tables
Base.metadata.create_all(engine)

# Achievement definitions
ACHIEVEMENTS = {
    # Commit-based achievements
    'first_commit': {
        'name': 'First Steps',
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
    
    # Code quantity achievements
    'code_writer': {
        'name': 'Code Writer',
        'description': 'Add 1000 lines of code',
        'points': 1000
    },
    'code_cleaner': {
        'name': 'Code Cleaner',
        'description': 'Delete 500 lines of code',
        'points': 800
    },
    'file_master': {
        'name': 'File Master',
        'description': 'Modify 10 different files',
        'points': 400
    },
    
    # Code quality achievements
    'message_pro': {
        'name': 'Message Pro',
        'description': 'Write a commit message longer than 100 characters',
        'points': 200
    },
    'multi_file': {
        'name': 'Multi-File Developer',
        'description': 'Modify 3 files in a single commit',
        'points': 300
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
    },
    
    # Project milestones
    'project_starter': {
        'name': 'Project Starter',
        'description': 'Create a new file in the project',
        'points': 100
    },
    'readme_writer': {
        'name': 'README Writer',
        'description': 'Create or update README.md',
        'points': 200
    },
    'dependency_master': {
        'name': 'Dependency Master',
        'description': 'Update requirements.txt',
        'points': 150
    }
}

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

def update_progress():
    """Update user progress based on git activity."""
    repo = get_git_repo()
    if not repo:
        return
    
    session = Session()
    progress = session.query(UserProgress).first()
    if not progress:
        progress = UserProgress()
        session.add(progress)
    
    # Get all commits
    all_commits = list(repo.iter_commits())
    
    # Find new commits since last update
    if progress.last_processed_commit:
        try:
            last_commit_index = next(i for i, c in enumerate(all_commits) 
                                   if c.hexsha == progress.last_processed_commit)
            new_commits = all_commits[:last_commit_index]
        except StopIteration:
            new_commits = all_commits
    else:
        new_commits = all_commits
    
    if not new_commits:
        session.close()
        return
    
    # Update the last processed commit
    progress.last_processed_commit = new_commits[0].hexsha
    
    # Update commit count
    progress.commits_count = len(all_commits)
    
    # Calculate points only for new commits
    new_points = 0
    for commit in new_commits:
        new_points += calculate_commit_points(commit)
    
    progress.total_points += new_points
    progress.last_updated = datetime.now()
    
    # Track commit times for streak and time-based achievements
    commit_times = [c.committed_datetime for c in all_commits]
    commit_dates = set(c.date() for c in commit_times)
    
    # Check only unlocked achievements
    unlocked_achievements = session.query(Achievement).filter(Achievement.unlocked_at.isnot(None)).all()
    unlocked_names = {a.name for a in unlocked_achievements}
    
    # Check achievements
    for achievement_id, achievement_data in ACHIEVEMENTS.items():
        if achievement_data['name'] in unlocked_names:
            continue
            
        achievement = session.query(Achievement).filter_by(name=achievement_data['name']).first()
        if not achievement:
            achievement = Achievement(
                name=achievement_data['name'],
                description=achievement_data['description'],
                points=achievement_data['points']
            )
            session.add(achievement)
        
        # Check if achievement should be unlocked
        if not achievement.unlocked_at:
            if achievement_id == 'first_commit' and progress.commits_count >= 1:
                achievement.unlocked_at = datetime.now()
                progress.total_points += achievement.points
            elif achievement_id == 'commit_master' and progress.commits_count >= 10:
                achievement.unlocked_at = datetime.now()
                progress.total_points += achievement.points
            elif achievement_id == 'commit_enthusiast':
                # Check for 5 commits in a single day
                commits_per_day = {}
                for commit_time in commit_times:
                    day = commit_time.date()
                    commits_per_day[day] = commits_per_day.get(day, 0) + 1
                if any(count >= 5 for count in commits_per_day.values()):
                    achievement.unlocked_at = datetime.now()
                    progress.total_points += achievement.points
            elif achievement_id == 'commit_streak':
                # Check for 3 consecutive days of commits
                sorted_dates = sorted(commit_dates)
                for i in range(len(sorted_dates) - 2):
                    if (sorted_dates[i+1] - sorted_dates[i]).days == 1 and \
                       (sorted_dates[i+2] - sorted_dates[i+1]).days == 1:
                        achievement.unlocked_at = datetime.now()
                        progress.total_points += achievement.points
                        break
            elif achievement_id == 'message_pro':
                # Check for long commit message
                if any(len(c.message) > 100 for c in all_commits):
                    achievement.unlocked_at = datetime.now()
                    progress.total_points += achievement.points
            elif achievement_id == 'multi_file':
                # Check for multi-file commit
                if any(len(c.stats.files) >= 3 for c in all_commits):
                    achievement.unlocked_at = datetime.now()
                    progress.total_points += achievement.points
            elif achievement_id == 'early_bird':
                # Check for early morning commit
                if any(c.committed_datetime.hour < 9 for c in all_commits):
                    achievement.unlocked_at = datetime.now()
                    progress.total_points += achievement.points
            elif achievement_id == 'night_owl':
                # Check for late night commit
                if any(c.committed_datetime.hour >= 21 for c in all_commits):
                    achievement.unlocked_at = datetime.now()
                    progress.total_points += achievement.points
    
    session.commit()
    session.close()

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

def clear_terminal():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_progress():
    """Display user progress and achievements."""
    clear_terminal()  # Clear the terminal before displaying new content
    
    session = Session()
    progress = session.query(UserProgress).first()
    achievements = session.query(Achievement).all()
    
    if not progress:
        console.print("[yellow]No progress recorded yet. Make some commits to get started![/yellow]")
        return
    
    # Get current and next rank
    current_rank = get_current_rank(progress.total_points)
    next_rank = get_next_rank(progress.total_points)
    
    # Calculate progress to next rank
    rank_progress = 0
    if next_rank:
        points_for_current = current_rank['points_required']
        points_for_next = next_rank['points_required']
        points_in_rank = points_for_next - points_for_current
        points_earned = progress.total_points - points_for_current
        rank_progress = (points_earned / points_in_rank) * 100 if points_in_rank > 0 else 100
    
    # Display progress
    console.print(Panel.fit(
        f"[bold green]Total Points: {progress.total_points}[/bold green]\n"
        f"Current Rank: {current_rank['emoji']} {current_rank['name']}\n"
        f"Commits: {progress.commits_count}\n"
        f"Last Updated: {progress.last_updated.strftime('%Y-%m-%d %H:%M:%S')}",
        title="Your Progress"
    ))
    
    # Display rank progress if there's a next rank
    if next_rank:
        console.print(Panel.fit(
            f"Progress to {next_rank['emoji']} {next_rank['name']}: {rank_progress:.1f}%\n"
            f"Points needed: {next_rank['points_required'] - progress.total_points}",
            title="Next Rank"
        ))
    
    # Display achievements
    table = Table(title="Achievements")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="magenta")
    table.add_column("Points", style="green")
    table.add_column("Status", style="yellow")
    
    for achievement in achievements:
        status = "✅ Unlocked" if achievement.unlocked_at else "🔒 Locked"
        table.add_row(
            achievement.name,
            achievement.description,
            str(achievement.points),
            status
        )
    
    console.print(table)
    session.close()

@app.command()
def start():
    """Start the code gamification system."""
    clear_terminal()  # Clear terminal at startup
    console.print("[bold green]Welcome to Code Game! 🎮[/bold green]")
    console.print("Tracking your coding progress...")
    
    while True:
        update_progress()
        display_progress()
        time.sleep(60)  # Update every minute

@app.command()
def status():
    """Show current progress and achievements."""
    display_progress()

if __name__ == "__main__":
    app() 