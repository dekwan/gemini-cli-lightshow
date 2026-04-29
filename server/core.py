import threading
import time
import random
import logging
from typing import List, Optional
from audio_playback import AudioPlayer
from hue import HueController
from color_utils import hue_sat_to_xy
from config import (
    BEAT_DELAY, DEFAULT_BRI, MAX_SAT, 
    MIN_RANDOM_BRI, MAX_BRI, FALLBACK_COLORS
)

logger = logging.getLogger("lightshow")

class LightShowApp:
    """Main application class to manage state and coordination."""
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.current_song: Optional[str] = None
        self.audio = AudioPlayer()
        self.hue = HueController()

    @property
    def is_playing(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start_show(self, song_path: str, colors: List[int], beats: List[float]) -> None:
        self.stop_show()
        self._stop_event.clear()
        self.current_song = song_path
        
        self.thread = threading.Thread(
            target=self._run_loop, 
            args=(song_path, colors, beats)
        )
        self.thread.daemon = True
        self.thread.start()

    def stop_show(self) -> None:
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                logger.warning("Lightshow thread did not exit cleanly.")
        
        self.audio.stop()
        self.current_song = None
        self.thread = None

    def _run_loop(self, song_path: str, colors: List[int], beat_times: List[float]) -> None:
        logger.info(f"Lightshow loop started for {song_path}")
        
        try:
            lights = self.hue.get_lights()
            
            if not colors:
                colors = FALLBACK_COLORS

            if colors:
                x, y = hue_sat_to_xy(colors[0], MAX_SAT)
                self.hue.set_group_state({
                    "on": {"on": True}, 
                    "dimming": {"brightness": (DEFAULT_BRI / 254.0) * 100.0}, 
                    "color": {"xy": {"x": x, "y": y}}
                })
            else:
                self.hue.turn_on()

            # Pre-calculate (x, y) coordinates for all available colors to avoid math in the hot loop
            color_xys = [hue_sat_to_xy(h, MAX_SAT) for h in colors]

            # Wait a bit for lights to react
            if self._stop_event.wait(timeout=0.5):
                return
                
            # Start playing audio AFTER the initial light setup
            if not self.audio.play(song_path):
                return

            start_time = time.time()
            beat_index = 0
            use_sync = len(beat_times) > 0
            
            # Hue network + hardware latency is approx 200-250ms. 
            # We artificially advance our 'elapsed' clock so the command is sent 
            # early, causing the physical light to hit its peak exactly ON the beat.
            sync_offset = 0.25 
            
            trigger_history = []

            while not self._stop_event.is_set():
                if not self.audio.is_playing():
                    logger.info("Playback finished")
                    break

                should_trigger = False
                if use_sync:
                    elapsed = (time.time() - start_time) + sync_offset
                    
                    if beat_index < len(beat_times) and elapsed >= beat_times[beat_index]:
                        should_trigger = True
                        beat_index += 1
                        # Skip beats only if we fell significantly behind to avoid
                        # skipping rapid consecutive beats or triggering bursts.
                        while beat_index < len(beat_times) and beat_times[beat_index] < elapsed - 0.1:
                            beat_index += 1
                    else:
                        # Sleep briefly to avoid busy loop, but check stop_event frequently
                        if self._stop_event.wait(timeout=0.01):
                            break
                else:
                    should_trigger = True
                    if self._stop_event.wait(timeout=BEAT_DELAY):
                        break

                if should_trigger:
                    now = time.time()
                    # Clean up history: only keep triggers from the last 1.0 seconds
                    trigger_history = [t for t in trigger_history if now - t < 1.0]
                    
                    if len(trigger_history) >= 3:
                        # Safety limiter: Prevent more than 3 flashes per second
                        # (WCAG 2.3.1 Three Flashes or Below Threshold for Photosensitive Epilepsy)
                        should_trigger = False
                    else:
                        trigger_history.append(now)

                if should_trigger and lights:
                    light_id = random.choice(lights)
                    bri = random.randint(MIN_RANDOM_BRI, MAX_BRI)
                    x, y = random.choice(color_xys)
                    
                    state = {
                        "on": {"on": True},
                        "color": {"xy": {"x": x, "y": y}},
                        "dimming": {"brightness": (bri / 254.0) * 100.0},
                        "dynamics": {"duration": 100}
                    }
                    self.hue.set_state(light_id, state)

        except Exception as e:
            logger.error(f"Error in lightshow loop: {e}")
        finally:
            logger.info("Lightshow loop exiting, cleaning up.")
            self.hue.set_gemini_gradient()
            # We don't stop audio here because stop_show calls audio.stop(), 
            # and if we just finished naturally, audio is already stopped.
