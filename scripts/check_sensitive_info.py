#!/usr/bin/env python3
"""
Script to check for sensitive information in the codebase.
This script helps identify API keys, tokens, and other sensitive information
that might have been accidentally committed to Git.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple, Set

# Define patterns for sensitive information
SENSITIVE_PATTERNS = [
    # API Keys
    (r'(?i)(api[-_]?key|apikey|api[-_]?token)[\s]*[:=][\s]*["\']([^"\']+)["\']', "API Key"),
    (r'(?i)([A-Za-z0-9_-]+)[-_]api[-_]key[\s]*[:=][\s]*["\']([^"\']+)["\']', "API Key"),
    
    # Google API Keys specific patterns
    (r'AIza[A-Za-z0-9_-]{35}', "Google API Key"),
    
    # AWS Keys
    (r'(?i)aws[-_]?access[-_]?key[-_]?id[\s]*[:=][\s]*["\']([^"\']+)["\']', "AWS Access Key"),
    (r'(?i)aws[-_]?secret[-_]?access[-_]?key[\s]*[:=][\s]*["\']([^"\']+)["\']', "AWS Secret Key"),
    (r'(?i)AKIA[A-Z0-9]{16}', "AWS Access Key ID"),
    
    # Database connection strings
    (r'(?i)(postgres|mysql|mongodb|sqlite)[:@][^:]+:[^@]+@[^/]+/[^"\']+', "Database Connection String"),
    
    # Passwords
    (r'(?i)(password|passwd|pwd)[\s]*[:=][\s]*["\']([^"\']+)["\']', "Password"),
    
    # Private keys
    (r'-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----', "Private Key"),
    
    # Tokens
    (r'(?i)(access[-_]?token|auth[-_]?token|app[-_]?token)[\s]*[:=][\s]*["\']([^"\']+)["\']', "Access Token"),
    
    # JWT Tokens
    (r'eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', "JWT Token"),
]

# Files and directories to ignore
IGNORE_DIRS = [
    '.git',
    'node_modules',
    'venv',
    'env',
    '.env',
    'api-env',
    'webscrape',
    'dist',
    'build',
    '__pycache__',
]

IGNORE_FILES = [
    '.gitignore',
    '.env.example',
    '*.md',  # Don't scan markdown files
    '*.log',
    '*.lock',
]

IGNORE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',  # Images
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',  # Documents
    '.zip', '.tar', '.gz', '.rar',  # Archives
    '.mp3', '.mp4', '.wav', '.avi',  # Media
    '.ttf', '.woff', '.woff2', '.eot',  # Fonts
]

def should_ignore(path: str) -> bool:
    """Determine if a file or directory should be ignored."""
    path_obj = Path(path)
    
    # Check if it's in an ignored directory
    for part in path_obj.parts:
        if part in IGNORE_DIRS:
            return True
    
    # Check file extension
    if path_obj.suffix.lower() in IGNORE_EXTENSIONS:
        return True
    
    # Check filename patterns
    for pattern in IGNORE_FILES:
        if '*' in pattern:
            if path_obj.match(pattern):
                return True
        elif path_obj.name == pattern:
            return True
    
    return False

def scan_file(file_path: str) -> List[Tuple[str, str, str, int]]:
    """Scan a file for sensitive information."""
    findings = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                for pattern, pattern_type in SENSITIVE_PATTERNS:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        # Get the matching text
                        matched_text = match.group(0)
                        # Limit the line to show context but not the full sensitive info
                        censored_line = line.strip()
                        if len(censored_line) > 100:
                            censored_line = censored_line[:50] + "..." + censored_line[-50:]
                        findings.append((file_path, pattern_type, censored_line, i))
    except (UnicodeDecodeError, IOError):
        # Skip binary files or files we can't read
        pass
    
    return findings

def get_staged_files() -> List[str]:
    """Get a list of files that are staged for commit."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True, text=True, check=False
        )
        return [file.strip() for file in result.stdout.splitlines() if file.strip()]
    except subprocess.SubprocessError:
        print("Warning: Could not get staged files from git.")
        return []

def get_committed_env_files() -> Set[str]:
    """Get a list of .env files that are tracked by Git."""
    try:
        result = subprocess.run(
            ['git', 'ls-files', '*env*', '*.env*', '.env*'],
            capture_output=True, text=True, check=False
        )
        return set(result.stdout.splitlines())
    except subprocess.SubprocessError:
        print("Warning: Could not check Git for tracked .env files.")
        return set()

def main():
    """Main function to scan the codebase for sensitive information."""
    # If called with --all flag, scan all files in the directory
    scan_all = "--all" in sys.argv
    
    root_dir = os.getcwd()
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        root_dir = sys.argv[1]
    
    print(f"Scanning {'all files' if scan_all else 'staged files'} in {root_dir} for sensitive information...")
    
    # Check for .env files in Git
    committed_env_files = get_committed_env_files()
    if committed_env_files:
        print("\n🚨 WARNING: The following .env files are tracked by Git:")
        for env_file in committed_env_files:
            print(f"  - {env_file}")
        print("\nThese files should be removed from Git tracking and added to .gitignore.")
        print("You can use: git rm --cached <file> to stop tracking them without deleting them.")
    
    # Scan for sensitive information
    findings = []
    
    if scan_all:
        # Scan all files in the directory
        for root, dirs, files in os.walk(root_dir):
            # Remove ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                file_path = os.path.join(root, file)
                if should_ignore(file_path):
                    continue
                
                file_findings = scan_file(file_path)
                findings.extend(file_findings)
    else:
        # Only scan staged files
        staged_files = get_staged_files()
        for file_path in staged_files:
            full_path = os.path.join(root_dir, file_path)
            if os.path.isfile(full_path) and not should_ignore(full_path):
                file_findings = scan_file(full_path)
                findings.extend(file_findings)
    
    # Print findings
    if findings:
        print(f"\n🚨 Found {len(findings)} potential sensitive information instances:")
        for file_path, pattern_type, line, line_num in findings:
            print(f"\n{file_path}:{line_num} - {pattern_type}")
            print(f"  {line}")
        
        print("\n⚠️  Please review these findings and ensure no sensitive information is committed to Git.")
        print("You may need to remove these secrets and replace them with environment variables.")
        print("For API keys that have been exposed, consider revoking and regenerating them.")
        sys.exit(1)
    else:
        print("✅ No sensitive information found in the scanned files.")
        sys.exit(0)

if __name__ == "__main__":
    main() 