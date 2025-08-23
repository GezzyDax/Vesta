#!/usr/bin/env python3
"""
Automatic version bumping based on git commit messages
Supports semantic versioning (MAJOR.MINOR.PATCH) with conventional commits
"""
import json
import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path


class VersionManager:
    def __init__(self, version_file="version.json"):
        self.version_file = Path(version_file)
        self.load_version()
    
    def load_version(self):
        """Load current version from file"""
        if self.version_file.exists():
            with open(self.version_file, 'r') as f:
                self.version_data = json.load(f)
        else:
            self.version_data = {
                "version": "1.0.0",
                "build": 1,
                "commit": "",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "name": "Vesta Family Budget"
            }
    
    def save_version(self):
        """Save version to file"""
        with open(self.version_file, 'w') as f:
            json.dump(self.version_data, f, indent=4)
    
    def get_current_version(self):
        """Get current version as tuple (major, minor, patch)"""
        version = self.version_data["version"]
        return tuple(map(int, version.split('.')))
    
    def set_version(self, major, minor, patch):
        """Set new version"""
        self.version_data["version"] = f"{major}.{minor}.{patch}"
        self.version_data["build"] += 1
        self.version_data["date"] = datetime.now().strftime("%Y-%m-%d")
    
    def get_git_info(self):
        """Get git commit info"""
        try:
            commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
            short_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
            commit_message = subprocess.check_output(['git', 'log', '-1', '--pretty=format:%s']).decode().strip()
            
            return {
                'commit': commit_hash,
                'short_hash': short_hash,
                'message': commit_message
            }
        except subprocess.CalledProcessError:
            return {
                'commit': 'unknown',
                'short_hash': 'unknown',
                'message': 'No commit message'
            }
    
    def analyze_commit_message(self, message):
        """
        Analyze commit message for version bump type
        Uses conventional commits format:
        - feat: new feature (minor bump)
        - fix: bug fix (patch bump)
        - BREAKING CHANGE: major bump
        - docs, style, refactor, test, chore: patch bump
        """
        message = message.lower()
        
        # Check for breaking changes
        if 'breaking change' in message or '!' in message.split(':')[0]:
            return 'major'
        
        # Check for features
        if message.startswith('feat:') or message.startswith('feature:'):
            return 'minor'
        
        # Check for fixes
        if message.startswith('fix:') or message.startswith('bugfix:'):
            return 'patch'
        
        # Check for other types
        if any(message.startswith(prefix) for prefix in ['docs:', 'style:', 'refactor:', 'test:', 'chore:', 'perf:']):
            return 'patch'
        
        # Default to patch for any other commit
        return 'patch'
    
    def bump_version(self, bump_type='auto'):
        """Bump version based on commit message or specified type"""
        git_info = self.get_git_info()
        
        if bump_type == 'auto':
            bump_type = self.analyze_commit_message(git_info['message'])
        
        major, minor, patch = self.get_current_version()
        
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        elif bump_type == 'patch':
            patch += 1
        
        self.set_version(major, minor, patch)
        self.version_data['commit'] = git_info['short_hash']
        
        return self.version_data['version']
    
    def generate_version_info(self):
        """Generate version info for the application"""
        git_info = self.get_git_info()
        
        return {
            **self.version_data,
            'full_version': f"v{self.version_data['version']}-{git_info['short_hash']}",
            'commit_message': git_info['message']
        }


def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatic version bumping')
    parser.add_argument('--type', choices=['auto', 'major', 'minor', 'patch'], default='auto',
                        help='Version bump type (default: auto based on commit message)')
    parser.add_argument('--show', action='store_true', help='Show current version')
    parser.add_argument('--file', default='version.json', help='Version file path')
    
    args = parser.parse_args()
    
    vm = VersionManager(args.file)
    
    if args.show:
        info = vm.generate_version_info()
        print(f"Current version: {info['full_version']}")
        print(f"Build: {info['build']}")
        print(f"Date: {info['date']}")
        print(f"Commit: {info['commit']}")
        if 'commit_message' in info:
            print(f"Last commit: {info['commit_message']}")
        return
    
    # Bump version
    old_version = vm.version_data['version']
    new_version = vm.bump_version(args.type)
    vm.save_version()
    
    print(f"Version bumped: {old_version} -> {new_version}")
    print(f"Build: {vm.version_data['build']}")


if __name__ == '__main__':
    main()