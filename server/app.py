"""
OpenEnv server entry point.
Re-exports the FastAPI app from the root app module.
"""
import sys
import os

# Add parent directory to path so we can import the root modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app  # noqa: F401


def main():
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
