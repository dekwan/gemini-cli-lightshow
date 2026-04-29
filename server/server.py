import os
import sys
import argparse
import time
import signal
import atexit
import logging
from mcp.server.fastmcp import FastMCP

# Import config to ensure logging and env vars are set up
import config
from core import LightShowApp
from audio_analysis import AudioAnalyzer

logger = logging.getLogger("lightshow")

# Initialize MCP Server
mcp = FastMCP("Hue Conductor")

import json

# Global app instance for MCP tools to access
app = LightShowApp()

def _get_available_songs():
    """Scans for audio files or loads from songs.json if available."""
    cwd = os.getcwd()
    json_path = os.path.join(cwd, "songs.json")
    
    # Check for hardcoded list in JSON
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading songs.json: {e}")

    # Fallback to dynamic scan
    extensions = ('.mp3', '.wav')
    files = [f for f in os.listdir(cwd) if f.lower().endswith(extensions)]
    return [{"file": f, "name": f} for f in sorted(files)]

@mcp.tool()
def set_color(hue: int, sat: int = 254, bri: int = 200) -> str:
    """Sets the lights to a specific hue (0-65535), saturation (0-254), and brightness (0-254)."""
    if not (0 <= hue <= 65535):
        return "Error: Hue must be between 0 and 65535."
    if not (0 <= sat <= 254):
        return "Error: Saturation must be between 0 and 254."
    if not (0 <= bri <= 254):
        return "Error: Brightness must be between 0 and 254."

    from color_utils import hue_sat_to_xy
    x, y = hue_sat_to_xy(hue, sat)
    
    state = {
        "on": {"on": True},
        "color": {"xy": {"x": x, "y": y}},
        "dimming": {"brightness": (bri / 254.0) * 100.0}
    }
    # Use try-except to catch potential connection errors
    try:
        app.hue.set_group_state(state)
        return f"Lights set to Hue: {hue}, Sat: {sat}, Bri: {bri}"
    except Exception as e:
        return f"Failed to set lights: {e}"

@mcp.tool()
def turn_on(bri: int = 150) -> str:
    """Sets the lights to a Gemini CLI logo gradient."""
    if not (0 <= bri <= 254):
        return "Error: Brightness must be between 0 and 254."

    try:
        app.hue.set_gemini_gradient(bri)
        return f"Lights set to Gemini gradient with brightness {bri}"
    except Exception as e:
        return f"Failed to turn on lights: {e}"

@mcp.tool()
def play_music(song_path: str) -> str:
    """Plays music with synchronized lights (auto-analyzed).
    Accepts a file path or a song number from list_songs.
    """
    actual_path = song_path
    songs = _get_available_songs()
    
    # Check if input is a number
    if song_path.isdigit():
        idx = int(song_path) - 1
        if 0 <= idx < len(songs):
            actual_path = os.path.join(os.getcwd(), songs[idx]["file"])
        else:
            return f"Error: Song number {song_path} is out of range (1-{len(songs)})."
    else:
        # If not an absolute path, resolve against CWD
        if not os.path.isabs(actual_path):
            actual_path = os.path.abspath(os.path.join(os.getcwd(), actual_path))

    if not os.path.exists(actual_path):
        return f"Error: File not found at {actual_path}."

    if not actual_path.lower().endswith(('.mp3', '.wav')):
        return "Error: Unsupported file format. Please use .mp3 or .wav."

    logger.info(f"Analyzing {actual_path}...")
    try:
        from color_utils import get_color_name
        data = AudioAnalyzer.analyze(actual_path)
        app.start_show(actual_path, 
                       data["hue_values"], 
                       data["beats"])
        hue_descriptions = [f"{h} ({get_color_name(h)})" for h in data["hue_values"]]
        hue_str = ", ".join(hue_descriptions)
        if data.get("gemini_used"):
            analysis_source = "analyzed lyrics"
        else:
            analysis_source = f"used default analysis. Error: {data.get('gemini_error', 'Unknown')}"
        
        lyrics_str = f"\n\nLyrics:\n{data['lyrics']}" if data.get('lyrics') else ""
        return f"Now playing {os.path.basename(actual_path)} with hue values {hue_str} ({analysis_source}){lyrics_str}"
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Error starting show: {e}"

@mcp.tool()
def turn_off() -> str:
    """Resets the system state (stops audio, resets lights to off)."""
    app.stop_show()
    time.sleep(0.5)
    app.hue.turn_on()
    time.sleep(0.5)
    app.hue.turn_off()
    return "System reset complete."

@mcp.tool()
def list_songs() -> str:
    """Lists available songs by genre with numbers."""
    songs = _get_available_songs()
    if not songs:
        return f"No .mp3 or .wav files found in {os.getcwd()}"

    lines = ["Available Songs:"]
    current_genre = None
    
    for i, song in enumerate(songs, 1):
        genre = song.get("genre")
        if genre and genre != current_genre:
            current_genre = genre
            lines.append(f"\n## **{current_genre}**")
        
        name = song.get("name", song["file"])
        lines.append(f"{i}. {name}")
        
    return "\n".join(lines).strip()


# --- Signal Handling & Cleanup ---
def cleanup_handler(signum, frame):
    logger.info("Received termination signal. cleaning up...")
    app.stop_show()
    app.hue.turn_off()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)

def atexit_handler():
    app.stop_show()
    app.hue.turn_off()

atexit.register(atexit_handler)

def main() -> None:
    parser = argparse.ArgumentParser(description="Hue Lightshow Controller")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser_set_color = subparsers.add_parser("set_color", help="Set all lights to a specific color")
    parser_set_color.add_argument("hue", type=int, help="Hue value (0-65535)")
    parser_set_color.add_argument("--sat", type=int, default=254, help="Saturation (0-254)")
    parser_set_color.add_argument("--bri", type=int, default=200, help="Brightness (0-254)")

    parser_turn_on = subparsers.add_parser("turn_on", help="Set lights to Gemini logo gradient")
    parser_turn_on.add_argument("--bri", type=int, default=150, help="Brightness (0-254)")

    parser_play = subparsers.add_parser("play_music", help="Play a music file with light synchronization")
    parser_play.add_argument("song_path", help="Path to the audio file")

    subparsers.add_parser("list_songs", help="List all available .mp3 files")
    subparsers.add_parser("turn_off", help="Reset system state")

    # If no arguments are provided, run the MCP server
    if len(sys.argv) == 1:
        logger.info("Starting MCP Server...")
        turn_on()
        try:
            mcp.run()
        except Exception as e:
            logger.error(f"MCP Server crashed: {e}")
            sys.exit(1)
    else:
        args = parser.parse_args()
        
        try:
            if args.command == "set_color":
                print(set_color(args.hue, args.sat, args.bri))
            elif args.command == "turn_on":
                print(turn_on(args.bri))
            elif args.command == "play_music":
                print(play_music(args.song_path))
                # Keep main thread alive while playing
                try:
                    while app.is_playing:
                        time.sleep(0.5)
                except KeyboardInterrupt:
                    app.stop_show()
            elif args.command == "list_songs":
                print(list_songs())
            elif args.command == "turn_off":
                print(turn_off())
            else:
                parser.print_help()
        except Exception as e:
            logger.error(f"Command failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
