"""
Git utilities for automatic versioning based on commits
"""
import subprocess
import os
from datetime import datetime
from typing import Optional, Dict, Any


class GitVersionManager:
    """Manages automatic versioning based on git commits"""
    
    def __init__(self, repo_path: str = '.'):
        self.repo_path = repo_path
    
    def get_current_commit_info(self) -> Dict[str, Any]:
        """Get information about the current git commit"""
        try:
            # Get commit hash
            commit_hash = self._run_git_command(['rev-parse', 'HEAD']).strip()
            
            # Get short commit hash
            short_hash = self._run_git_command(['rev-parse', '--short', 'HEAD']).strip()
            
            # Get commit message
            commit_message = self._run_git_command(['log', '-1', '--pretty=format:%s']).strip()
            
            # Get commit author
            author = self._run_git_command(['log', '-1', '--pretty=format:%an']).strip()
            
            # Get commit date
            commit_date_str = self._run_git_command(['log', '-1', '--pretty=format:%ci']).strip()
            commit_date = datetime.strptime(commit_date_str, '%Y-%m-%d %H:%M:%S %z')
            
            # Get branch name
            try:
                branch = self._run_git_command(['rev-parse', '--abbrev-ref', 'HEAD']).strip()
            except:
                branch = 'unknown'
            
            # Get tag if exists
            try:
                tag = self._run_git_command(['describe', '--tags', '--exact-match', 'HEAD']).strip()
            except:
                tag = None
            
            return {
                'commit_hash': commit_hash,
                'short_hash': short_hash,
                'commit_message': commit_message,
                'author': author,
                'commit_date': commit_date,
                'branch': branch,
                'tag': tag,
                'version_name': self._generate_version_name(short_hash, commit_message, tag, branch)
            }
            
        except Exception as e:
            return {
                'commit_hash': 'unknown',
                'short_hash': 'unknown',
                'commit_message': 'No git info available',
                'author': 'System',
                'commit_date': datetime.now(),
                'branch': 'unknown',
                'tag': None,
                'version_name': f'Manual Version {datetime.now().strftime("%Y%m%d-%H%M%S")}'
            }
    
    def _generate_version_name(self, short_hash: str, commit_message: str, tag: Optional[str], branch: str) -> str:
        """Generate a human-readable version name"""
        if tag:
            return f"Release {tag} ({short_hash})"
        
        # Clean commit message (first line only, max 50 chars)
        clean_message = commit_message.split('\n')[0][:50]
        
        if branch == 'main' or branch == 'master':
            return f"v{short_hash}: {clean_message}"
        else:
            return f"[{branch}] {short_hash}: {clean_message}"
    
    def _run_git_command(self, args: list) -> str:
        """Run a git command and return output"""
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {' '.join(args)}: {e.stderr}")
    
    def is_git_repository(self) -> bool:
        """Check if current directory is a git repository"""
        try:
            self._run_git_command(['rev-parse', '--git-dir'])
            return True
        except:
            return False
    
    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes"""
        try:
            status = self._run_git_command(['status', '--porcelain']).strip()
            return len(status) > 0
        except:
            return False
    
    def get_commit_stats(self) -> Dict[str, int]:
        """Get statistics about the current commit"""
        try:
            # Get file changes
            stats = self._run_git_command(['diff', '--stat', 'HEAD~1..HEAD']).strip()
            
            # Parse insertions and deletions
            insertions = 0
            deletions = 0
            files_changed = 0
            
            if stats:
                lines = stats.split('\n')
                for line in lines[:-1]:  # Skip summary line
                    files_changed += 1
                
                # Parse summary line
                summary = lines[-1] if lines else ""
                if 'insertion' in summary:
                    insertions = int(summary.split(' insertion')[0].split('+')[-1].strip())
                if 'deletion' in summary:
                    deletions = int(summary.split(' deletion')[0].split('-')[-1].strip())
            
            return {
                'files_changed': files_changed,
                'insertions': insertions,
                'deletions': deletions
            }
        except:
            return {
                'files_changed': 0,
                'insertions': 0,
                'deletions': 0
            }


def create_git_based_version_description(commit_info: Dict[str, Any], stats: Dict[str, int]) -> str:
    """Create a detailed version description based on git commit info"""
    description_parts = [
        f"Git commit: {commit_info['short_hash']}",
        f"Branch: {commit_info['branch']}",
        f"Author: {commit_info['author']}",
        f"Message: {commit_info['commit_message']}"
    ]
    
    if stats['files_changed'] > 0:
        description_parts.append(
            f"Changes: {stats['files_changed']} files, "
            f"+{stats['insertions']} insertions, "
            f"-{stats['deletions']} deletions"
        )
    
    if commit_info['tag']:
        description_parts.insert(0, f"Tagged release: {commit_info['tag']}")
    
    return '\n'.join(description_parts)