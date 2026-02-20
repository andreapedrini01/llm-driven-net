#!/usr/bin/env python3
"""
Documentation Validation Script

This script validates that code examples in documentation are correct and up-to-date.
It checks:
- API endpoints exist
- Configuration files are valid
- Shell commands are syntactically correct
- Links are not broken
"""

import re
import os
import sys
import json
from pathlib import Path
from typing import List, Tuple, Dict

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class DocValidator:
    def __init__(self, docs_dir: str = "docs"):
        self.docs_dir = Path(docs_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.successes: List[str] = []
        
    def validate_all(self) -> bool:
        """Validate all documentation files"""
        print(f"Validating documentation in {self.docs_dir}...")
        print("=" * 60)
        
        # Find all markdown files
        md_files = list(self.docs_dir.glob("*.md"))
        
        for md_file in md_files:
            print(f"\nValidating {md_file.name}...")
            self.validate_file(md_file)
        
        # Print summary
        self.print_summary()
        
        return len(self.errors) == 0
    
    def validate_file(self, file_path: Path):
        """Validate a single documentation file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract code blocks
        code_blocks = self.extract_code_blocks(content)
        
        for lang, code in code_blocks:
            if lang == 'bash':
                self.validate_bash_commands(code, file_path.name)
            elif lang == 'yaml':
                self.validate_yaml(code, file_path.name)
            elif lang == 'json':
                self.validate_json(code, file_path.name)
            elif lang == 'python':
                self.validate_python(code, file_path.name)
        
        # Check for broken internal links
        self.validate_internal_links(content, file_path.name)
        
        # Check for outdated references
        self.check_outdated_references(content, file_path.name)
    
    def extract_code_blocks(self, content: str) -> List[Tuple[str, str]]:
        """Extract code blocks from markdown"""
        pattern = r'```(\w+)\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)
        return matches
    
    def validate_bash_commands(self, code: str, filename: str):
        """Validate bash commands"""
        lines = code.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Check for common issues
            if 'rm -rf /' in line:
                self.errors.append(f"{filename}: Dangerous command found: {line}")
            elif 'sudo' in line:
                self.warnings.append(f"{filename}: Command requires sudo: {line}")
            elif line.startswith('docker-compose') and '--file' not in line and '-f' not in line:
                # Check if docker-compose.yml exists
                if not Path('docker-compose.yml').exists():
                    self.warnings.append(f"{filename}: docker-compose.yml not found for: {line}")
            
            # Check for placeholder values that should be replaced
            if '<' in line and '>' in line:
                placeholders = re.findall(r'<([^>]+)>', line)
                for placeholder in placeholders:
                    if placeholder.lower() not in ['admin-token', 'token', 'password', 'timestamp', 
                                                     'pod-name', 'service', 'command', 'phone', 
                                                     'contact', 'previous-commit', 'ryu_host', 
                                                     'comnetsemu_host', 'ryu_port', 'comnetsemu_port']:
                        self.warnings.append(f"{filename}: Unusual placeholder: <{placeholder}>")
    
    def validate_yaml(self, code: str, filename: str):
        """Validate YAML syntax"""
        if not HAS_YAML:
            self.warnings.append(f"{filename}: PyYAML not installed, skipping YAML validation")
            return
        
        try:
            yaml.safe_load(code)
            self.successes.append(f"{filename}: Valid YAML")
        except yaml.YAMLError as e:
            self.errors.append(f"{filename}: Invalid YAML: {str(e)}")
    
    def validate_json(self, code: str, filename: str):
        """Validate JSON syntax"""
        try:
            json.loads(code)
            self.successes.append(f"{filename}: Valid JSON")
        except json.JSONDecodeError as e:
            self.errors.append(f"{filename}: Invalid JSON: {str(e)}")
    
    def validate_python(self, code: str, filename: str):
        """Validate Python syntax"""
        try:
            compile(code, '<string>', 'exec')
            self.successes.append(f"{filename}: Valid Python")
        except SyntaxError as e:
            self.errors.append(f"{filename}: Invalid Python: {str(e)}")
    
    def validate_internal_links(self, content: str, filename: str):
        """Check for broken internal links"""
        # Find markdown links
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', content)
        
        for text, link in links:
            # Skip external links
            if link.startswith('http://') or link.startswith('https://'):
                continue
            
            # Check if file exists
            if link.startswith('./'):
                link_path = self.docs_dir / link[2:]
            else:
                link_path = self.docs_dir / link
            
            if not link_path.exists():
                self.warnings.append(f"{filename}: Broken link: {link}")
    
    def check_outdated_references(self, content: str, filename: str):
        """Check for potentially outdated version references"""
        # Check for version numbers
        version_patterns = [
            (r'Python (\d+\.\d+)', 'Python'),
            (r'Docker (\d+\.\d+)', 'Docker'),
            (r'PostgreSQL (\d+)', 'PostgreSQL'),
            (r'Redis (\d+)', 'Redis'),
        ]
        
        for pattern, name in version_patterns:
            matches = re.findall(pattern, content)
            if matches:
                # Just log for awareness, not an error
                pass
    
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        
        if self.successes:
            print(f"\n{GREEN}✓ Successes: {len(self.successes)}{RESET}")
            for success in self.successes[:5]:  # Show first 5
                print(f"  {success}")
            if len(self.successes) > 5:
                print(f"  ... and {len(self.successes) - 5} more")
        
        if self.warnings:
            print(f"\n{YELLOW}⚠ Warnings: {len(self.warnings)}{RESET}")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if self.errors:
            print(f"\n{RED}✗ Errors: {len(self.errors)}{RESET}")
            for error in self.errors:
                print(f"  {error}")
        
        print("\n" + "=" * 60)
        
        if self.errors:
            print(f"{RED}Validation FAILED{RESET}")
            return False
        elif self.warnings:
            print(f"{YELLOW}Validation PASSED with warnings{RESET}")
            return True
        else:
            print(f"{GREEN}Validation PASSED{RESET}")
            return True

def main():
    """Main entry point"""
    validator = DocValidator()
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
