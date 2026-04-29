import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lightshow.log")
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("lightshow")

# Load configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
env_path_local = os.path.join(current_dir, ".env")
env_path_root = os.path.join(project_root, ".env")

# Load root .env first, then local .env (local overrides root)
if os.path.exists(env_path_root):
    load_dotenv(env_path_root)
if os.path.exists(env_path_local):
    load_dotenv(env_path_local, override=True)

HUE_BRIDGE_IP = os.getenv("HUE_BRIDGE_IP")
HUE_USERNAME = os.getenv("HUE_USERNAME")

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not HUE_BRIDGE_IP or not HUE_USERNAME:
    logger.warning("HUE_BRIDGE_IP or HUE_USERNAME not found in environment variables. Light sync will fail.")

# Check if at least one authentication method is available
vertex_ai_configured = GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION and GOOGLE_GENAI_USE_VERTEXAI
if not GEMINI_API_KEY and not vertex_ai_configured:
    logger.warning("Neither GEMINI_API_KEY nor Vertex AI environment variables (GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_GENAI_USE_VERTEXAI) found. Gemini analysis may fail.")

BASE_URL = f"https://{HUE_BRIDGE_IP}/clip/v2"
BEAT_DELAY = 0.5

# Hue Constants
MAX_HUE = 65535
HUE_ORANGE = 12750
HUE_CYAN = 46920

MAX_SAT = 254
MAX_BRI = 254
DEFAULT_BRI = 200
MIN_RANDOM_BRI = 150

# Audio Analysis Constants
CHROMA_BINS = 12.0
SPECTRAL_CENTROID_MIN = 500
SPECTRAL_CENTROID_RANGE = 4500
TEMPO_MIN = 60
TEMPO_RANGE = 120

# Gemini Configuration
GEMINI_COLORS_XY = [
    (0.1515, 0.0472), # Gemini Blue (Deep Saturated)
    (0.1356, 0.0426), # Gemini Light Blue (Deep Saturated)
    (0.1379, 0.0861), # Gemini Cyan (Shifted to strong primary)
    (0.4288, 0.1745)  # Gemini Purple/Rose (Deep Saturated)
]

GEMINI_PROMPT = (
    "Analyze the lyrics, mood, and theme of this song. "
    "Return a JSON object with two keys: "
    "1. 'hues': A list of 5 integer Hue values (0 to 65535) that best represent the colors of this theme. "
    "For example, a Halloween song might use oranges, greens, and purples. "
    "2. 'lyrics': A string containing the transcribed lyrics of the song, "
    "formatted with line breaks and structure (e.g., [Verse], [Chorus]) like a real song. "
    "In the lyrics, ensure that 'Gemini CLI' is always spelled correctly as 'Gemini CLI' (not 'Gemini see lie' or 'Gemini see life'). "
    "Output ONLY valid JSON, no markdown formatting or other text. "
    "Example: {\"hues\": [12000, 34000, 50000, 55000, 10000], \"lyrics\": \"[Verse 1]\\nSong lyrics line 1...\"}"
)

# Color Fallbacks & Thresholds
FALLBACK_COLORS = [0, HUE_ORANGE, HUE_CYAN]

COLOR_THRESHOLDS = [
    (2500, "Red"),
    (8500, "Orange"),
    (16000, "Yellow"),
    (30000, "Green"),
    (40000, "Cyan"),
    (50000, "Blue"),
    (58000, "Purple"),
    (63000, "Pink"),
    (65535, "Red")
]