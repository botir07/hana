# HANA (Beta)

HANA is an early-stage desktop assistant with a floating avatar and chat UI.

## Status
- Beta: features and stability are still in progress.
- Expect bugs, missing features, and breaking changes.

## What Works
- Avatar window (2D VTuber style by default; drop PNG frames into `assets/waifu2d`)
- 3D avatar window (Panda3D) if `HANA_AVATAR_MODE=3d`
- Chat window (Qt/PySide6)
- Right-click system menu on the avatar (Ctrl + right-click)

## Requirements
- Windows 11
- Python 3.10+
- OpenRouter API key
- (Optional) Tesseract OCR installed and added to PATH for live screen reading

## Setup
1) Create and activate a virtual environment
2) Install dependencies:
   `pip install -r requirements.txt`
3) Run:
   `python main.py`
4) (Optional) Switch avatar renderer:
   - 2D (default): `HANA_AVATAR_MODE=2d`
   - 3D Panda3D model: `HANA_AVATAR_MODE=3d`

## Notes
- Chat uses OpenRouter free models and may be rate-limited.
- If responses fail, try again later.
- Live screen reader (Settings bar -> Screen: ON) captures the primary monitor every ~1.5s, runs OCR, and reads recognized text aloud. Install Tesseract to enable it; without it the feature will show a warning.

## License
TBD
