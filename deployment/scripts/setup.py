#!/usr/bin/env python3
"""Setup script for development environment."""

import subprocess
import sys
import os


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return None


def main():
    """Main setup function."""
    print("Setting up LLM Integration Module development environment...\n")
    
    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 or higher is required")
        sys.exit(1)
    
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install basic dependencies
    basic_deps = [
        "pydantic",
        "fastapi", 
        "uvicorn",
        "pytest",
        "hypothesis"
    ]
    
    for dep in basic_deps:
        result = run_command(f"pip install {dep}", f"Installing {dep}")
        if result is None:
            print(f"⚠️  Failed to install {dep}, continuing...")
    
    # Verify setup
    print("\nVerifying setup...")
    result = run_command("python test_setup.py", "Running setup verification")
    
    if result:
        print("\n🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and configure your settings")
        print("2. Start implementing the services in src/services/")
        print("3. Add API routes in src/api/")
        print("4. Run tests with: pytest")
        print("5. Start the development server with: python -m src.main")
    else:
        print("\n❌ Setup verification failed. Please check the errors above.")


if __name__ == "__main__":
    main()