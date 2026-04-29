import os
import logging
import librosa
import numpy as np
import json
import time
import concurrent.futures
from google import genai
from google.genai import types
from typing import Dict, Any, Tuple
from config import (
    MAX_HUE, HUE_CYAN, CHROMA_BINS, SPECTRAL_CENTROID_MIN, 
    SPECTRAL_CENTROID_RANGE, TEMPO_MIN, TEMPO_RANGE, GEMINI_PROMPT,
    GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_GENAI_USE_VERTEXAI,
    GEMINI_API_KEY
)

logger = logging.getLogger("lightshow")

class AudioAnalyzer:
    """Encapsulates all audio analysis logic using librosa."""
    
    @staticmethod
    def _get_gemini_data(file_path: str) -> Tuple[Dict[str, Any], str]:
        """Runs the Gemini API call and returns (data_dict, error_msg)."""
        try:
            # Logic: If GOOGLE_GENAI_USE_VERTEXAI is found, use vertexai, if not, use gemini api key.
            # Convert to string and check if it's "true" (case-insensitive) or just truthy
            use_vertexai = str(GOOGLE_GENAI_USE_VERTEXAI).lower() == "true"
            
            if use_vertexai:
                logger.info("Sending audio to Gemini (Vertex AI) for theme analysis...")
                client = genai.Client(
                    vertexai=True, 
                    project=GOOGLE_CLOUD_PROJECT, 
                    location=GOOGLE_CLOUD_LOCATION
                )
            else:
                logger.info("Sending audio to Gemini (API Key) for theme analysis...")
                client = genai.Client(api_key=GEMINI_API_KEY)
            
            with open(file_path, "rb") as f:
                audio_bytes = f.read()
            
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3")

            # Add retry logic for transient 500 errors
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model='gemini-3-flash-preview',
                        contents=[audio_part, GEMINI_PROMPT],
                        config={
                            'response_mime_type': 'application/json',
                        }
                    )
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Gemini API attempt {attempt+1} failed: {e}. Retrying...")
                    time.sleep(2)
                        
            if response:
                logger.info(f"Gemini analysis response: {response.text}")
                # With response_mime_type='application/json', we get raw JSON
                data = json.loads(response.text.strip())
                if not isinstance(data, dict) or 'hues' not in data or 'lyrics' not in data:
                    raise ValueError("Invalid JSON format from Gemini. Expected keys: 'hues', 'lyrics'.")
                return data, ""
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}. Falling back to librosa chroma analysis.")
            return {}, str(e)
            
        return {}, "Unknown Gemini Error"

    @staticmethod
    def _enforce_flash_safety(beat_times: np.ndarray) -> np.ndarray:
        """
        Enforces the WCAG General Flash Threshold for photosensitive epilepsy.
        Ensures there are never more than 3 flashes within any 1-second rolling window.
        """
        if len(beat_times) == 0:
            return beat_times

        safe_beats = []
        for t in beat_times:
            # Count how many beats in the safe list occurred within the last 1.0 second of 't'
            recent_beats = [b for b in safe_beats if 0 <= (t - b) <= 1.0]
            
            # If we have 3 or more beats in the last second, adding this one would equal 4.
            # So we drop this beat to stay under the limit.
            if len(recent_beats) < 3:
                safe_beats.append(t)
                
        return np.array(safe_beats)

    @staticmethod
    def analyze(file_path: str) -> Dict[str, Any]:
        """Calculates audio features and hue values for a given audio file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Error: {file_path} not found.")

        try:
            hues = []
            lyrics = None
            gemini_used = False
            gemini_error = None
            
            # Start Gemini analysis in parallel with librosa processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                gemini_future = executor.submit(AudioAnalyzer._get_gemini_data, file_path)

                # Load the file for local analysis - explicitly downsample to speed up processing
                y, sr = librosa.load(file_path, sr=11025)
                
                # Beat tracking
                tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, tightness=95)
                beat_times = librosa.frames_to_time(beat_frames, sr=sr)
                
                # Extrapolate beats to the end of the song if there's a gap
                duration = librosa.get_duration(y=y, sr=sr)
                tempo_val = float(tempo.item() if isinstance(tempo, np.ndarray) else tempo)
                
                if tempo_val > 0 and len(beat_times) > 0:
                    beat_interval = 60.0 / tempo_val
                    last_beat = beat_times[-1]
                    new_beats = list(beat_times)
                    # Use a small buffer (0.5s) to avoid triggering a beat EXACTLY at the file's end
                    while last_beat + beat_interval < duration - 0.5:
                        last_beat += beat_interval
                        new_beats.append(last_beat)
                    beat_times = np.array(new_beats)

                # Spectral Centroid (Brightness)
                cent = librosa.feature.spectral_centroid(y=y, sr=sr)
                norm_cent = np.clip((np.mean(cent) - SPECTRAL_CENTROID_MIN) / SPECTRAL_CENTROID_RANGE, 0, 1)

                # Tempo
                tempo_val = float(tempo.item() if isinstance(tempo, np.ndarray) else tempo)
                norm_tempo = np.clip((tempo_val - TEMPO_MIN) / TEMPO_RANGE, 0, 1)

                # Wait for Gemini result
                gemini_data, gemini_error = gemini_future.result()
                hues = gemini_data.get("hues", [])
                lyrics = gemini_data.get("lyrics")
                gemini_used = bool(hues)

            if not hues:
                # Chroma analysis for color mapping (Fallback)
                # Optimize fallback by only analyzing a maximum of 30 seconds from the middle
                duration_samples = len(y)
                thirty_seconds = sr * 30
                
                if duration_samples > thirty_seconds:
                    start = (duration_samples - thirty_seconds) // 2
                    y_chroma = y[start:start + thirty_seconds]
                else:
                    y_chroma = y
                    
                chroma = librosa.feature.chroma_stft(y=y_chroma, sr=sr)
                mean_chroma = np.mean(chroma, axis=1)
                top_indices = np.argsort(mean_chroma)[-3:][::-1]
                hues = [int((idx / CHROMA_BINS) * MAX_HUE) for idx in top_indices]
                
                # Only add the calculated brightness/tempo cyans if using fallback
                hues.append(int(norm_cent * HUE_CYAN))
                hues.append(int((1 - norm_tempo) * HUE_CYAN))

            # Apply Photosensitivity Flash Filter
            if isinstance(beat_times, list):
                beat_times = np.array(beat_times)
            beat_times = AudioAnalyzer._enforce_flash_safety(beat_times)

            return {
                "beats": beat_times.tolist() if hasattr(beat_times, "tolist") else list(beat_times),
                "tempo": tempo_val,
                "hue_values": hues,
                "lyrics": lyrics,
                "gemini_used": gemini_used,
                "gemini_error": gemini_error
            }
        except Exception as e:
            logger.error(f"Failed to analyze audio file {file_path}: {e}")
            raise RuntimeError(f"Audio analysis failed: {e}")