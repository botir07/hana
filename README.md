# HANA (Beta)

HANA is an early-stage desktop assistant with a floating avatar and chat UI.

## Status
- Beta: features and stability are still in progress.
- Expect bugs, missing features, and breaking changes.

## What Works
- Avatar window (Panda3D)
- Chat window (Qt/PySide6)
- Right-click system menu on the avatar (Ctrl + right-click)

## Requirements
- Windows 11
- Python 3.10+
- OpenRouter API key

## Setup
1) Create and activate a virtual environment
2) Install dependencies:
   `pip install -r requirements.txt`
3) Run:
   `python main.py`

## Notes
- Chat uses OpenRouter free models and may be rate-limited.
- If responses fail, try again later.

## License
TBD
