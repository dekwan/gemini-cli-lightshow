# Gemini CLI Lightshow MCP

This project is a **local** Model Context Protocol (MCP) server that transforms your room into a synchronized lightshow using Philips Hue lights and Gemini's AI-driven audio analysis. 

> **Note:** Since this server communicates with your Philips Hue Bridge over your local network, it must be run on a machine that is on the same network as your Hue Bridge.

## Features

- **Gemini Theme Analysis:** Uses Gemini (via API Key or Vertex AI) to analyze the mood, lyrics, and theme of a song to generate a representative color palette.
- **Beat-Synchronized Lighting:** Real-time audio analysis using `librosa` for precise beat tracking.
- **Epilepsy Safety:** Implements WCAG 2.3.1 General Flash Threshold filters to ensure a safe visual experience.
- **MCP Integration:** Exposes tools to control lights and play music directly from the Gemini CLI.

## Setup

### 1. Prerequisites

- **Philips Hue Bridge:** A Hue Bridge on your local network.
- **Python 3.10+**
- **FFmpeg:** Required for audio processing. Install via:
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt update && sudo apt install ffmpeg`

### 2. Installation

Install the extension directly via the Gemini CLI:

```bash
gemini extensions install https://github.com/dekwan/gemini-cli-lightshow
```

### 3. Configuration & Authentication

The Gemini CLI Lightshow MCP requires access to the Gemini model for audio and lyric analysis. You can authenticate using **either** a Gemini API Key (easier setup) **or** Google Cloud Vertex AI.

Create a `.env` file in the `~/.gemini/extensions/lightshow/server/` directory (or the root directory) with your Philips Hue credentials and ONE of the authentication methods below.

```env
# Philips Hue Configuration (Required)
HUE_BRIDGE_IP=your_bridge_ip
HUE_USERNAME=your_hue_username
```

#### How to get your Hue Bridge IP and Username:

1. **Find your Bridge IP:** 
   - Open the Philips Hue app: **Settings > Bridges > Your_Bridge > IP-address.
   - Or run this in your terminal: `curl https://discovery.meethue.com/`
2. **Create a Username:**
   - **Press the physical link button** on top of your Hue Bridge.
   - Within 30 seconds, run this in your terminal:
     ```bash
     curl -X POST -d '{"devicetype":"gemini_lightshow"}' http://<YOUR_BRIDGE_IP>/api
     ```
   - Your `username` will be in the response. Copy it into your `.env` file.

#### Option A: Gemini API Key (Recommended for simplicity)

Get an API key and add it to your `.env` file in your project directory or home directory:

```env
# Gemini API Key Configuration
GEMINI_API_KEY=your_api_key_here
```

#### Option B: Google Cloud Vertex AI

If you prefer using Vertex AI, ensure your Google Cloud Project has the Vertex AI API enabled, and add the following to your `.env` file in your project directory or home directory:

```env
# Vertex AI Configuration
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=your_location
GOOGLE_GENAI_USE_VERTEXAI=True
```

For Vertex AI, you must also authenticate your local environment with Google Cloud:

```bash
gcloud auth application-default login
```

### 4. Adding Music

The server scans for audio files in the directory where you launch Gemini CLI.

1. **Add MP3s:** Place your `.mp3` files in the directory where you plan to run the `gemini` command.
2. **(Optional) Organize with `songs.json`:** 
   - Create a `songs.json` file in that same directory (you can copy the format from `songs.json.example`).
   - Update the entries to match your file names and preferred display names.

## Usage

This server communicates over `stdio`, making it compatible with any MCP client.

### Run via Gemini CLI

Once installed via `gemini extensions install`, you can use the following tools in your Gemini CLI session:

- `mcp_lightshow_list_songs`: Shows available `.mp3` tracks.
- `mcp_lightshow_play_music`: Plays a song (by number or path) with synchronized lighting.
- `mcp_lightshow_set_color`: Sets a static hue/sat/bri.
- `mcp_lightshow_turn_on`: Resets lights to the Gemini logo gradient.
- `mcp_lightshow_turn_off`: Resets and turns off lights.

### Run via Other MCP Clients (e.g., Claude Desktop, Cursor)

You can add this server to any standard MCP client. The `start_server.sh` script handles setting up the environment and launching the server.

Add the following to your client's MCP configuration:

```json
{
  "mcpServers": {
    "lightshow": {
      "command": "bash",
      "args": ["/absolute/path/to/gemini-cli-lightshow/server/start_server.sh"]
    }
  }
}
```

*Note: Replace `/absolute/path/to/...` with the actual path to your cloned repository.*

## Credits

All code in this repository was written by the Gemini CLI. Powered by Google Gemini and Philips Hue.