"""
Application version management
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any


class AppVersion:
    """Application version manager"""
    
    def __init__(self, version_file: str = "version.json"):
        self.version_file = Path(version_file)
        self._version_data = None
    
    def get_version_info(self) -> Dict[str, Any]:
        """Get complete version information"""
        if self._version_data is None:
            self._load_version()
        
        # Add git info if available
        git_info = self._get_git_info()
        
        return {
            **self._version_data,
            'full_version': f"v{self._version_data['version']}-{git_info['short_hash']}",
            'git_commit': git_info['commit'],
            'git_short_hash': git_info['short_hash'],
            'git_branch': git_info['branch'],
            'git_dirty': git_info['dirty']
        }
    
    def _load_version(self):
        """Load version from file"""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r') as f:
                    self._version_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self._version_data = self._default_version()
        else:
            self._version_data = self._default_version()
    
    def _default_version(self) -> Dict[str, Any]:
        """Default version data"""
        return {
            "version": "1.0.0",
            "build": 1,
            "commit": "unknown",
            "date": "2025-08-24",
            "name": "Vesta Family Budget"
        }
    
    def _get_git_info(self) -> Dict[str, str]:
        """Get git information"""
        # First try to read from build_info.json (Docker build)
        build_info_path = Path("build_info.json")
        if build_info_path.exists():
            try:
                with open(build_info_path, 'r') as f:
                    build_info = json.load(f)
                    commit = build_info.get('git_commit', 'unknown')
                    branch = build_info.get('git_branch', 'unknown')
                    
                    # Create short hash from full commit
                    short_hash = commit[:7] if len(commit) > 7 else commit
                    
                    return {
                        'commit': commit,
                        'short_hash': short_hash,
                        'branch': branch,
                        'dirty': False  # Docker build is always clean
                    }
            except (json.JSONDecodeError, FileNotFoundError, KeyError):
                pass
        
        # Fallback to git commands (development environment)
        try:
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
            short_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
            
            # Check if working directory is dirty
            try:
                subprocess.check_output(['git', 'diff-index', '--quiet', 'HEAD'], stderr=subprocess.DEVNULL)
                dirty = False
            except subprocess.CalledProcessError:
                dirty = True
            
            return {
                'commit': commit,
                'short_hash': short_hash,
                'branch': branch,
                'dirty': dirty
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {
                'commit': 'unknown',
                'short_hash': 'unknown',
                'branch': 'unknown',
                'dirty': False
            }
    
    def get_version_string(self) -> str:
        """Get version string for display"""
        info = self.get_version_info()
        version_str = info['full_version']
        
        if info['git_dirty']:
            version_str += '-dirty'
        
        if info['git_branch'] != 'main' and info['git_branch'] != 'master':
            version_str += f" ({info['git_branch']})"
        
        return version_str
    
    def get_simple_version(self) -> str:
        """Get simple version number"""
        if self._version_data is None:
            self._load_version()
        return self._version_data['version']


# Global instance
app_version = AppVersion()


def get_app_version() -> str:
    """Get application version string"""
    return app_version.get_version_string()


def get_version_info() -> Dict[str, Any]:
    """Get complete version information"""
    return app_version.get_version_info()