import os
# Suppress the welcome message from pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'

import pygame
import logging

logger = logging.getLogger("lightshow")

class AudioPlayer:
    """Encapsulates all audio playback logic using pygame."""
    _initialized: bool = False

    @classmethod
    def _ensure_init(cls) -> None:
        if not cls._initialized:
            try:
                pygame.mixer.init()
                cls._initialized = True
            except pygame.error as e:
                logger.error(f"Failed to initialize audio mixer: {e}")

    @classmethod
    def play(cls, file_path: str) -> bool:
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False

        cls._ensure_init()
        try:
            if pygame.mixer.music.get_busy():
                cls.stop()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            logger.info(f"Audio playback started: {file_path}")
            return True
        except pygame.error as e:
            logger.error(f"Audio playback error: {e}")
            return False

    @classmethod
    def stop(cls) -> None:
        if cls._initialized:
            try:
                pygame.mixer.music.stop()
                logger.info("Audio playback stopped")
            except pygame.error as e:
                logger.warning(f"Error stopping audio: {e}")

    @classmethod
    def get_pos(cls) -> float:
        if not cls._initialized:
            return 0.0
        try:
            if not pygame.mixer.music.get_busy():
                return 0.0
            return pygame.mixer.music.get_pos() / 1000.0
        except Exception:
            return 0.0

    @classmethod
    def is_playing(cls) -> bool:
        if not cls._initialized:
            return False
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False
    
    @classmethod
    def cleanup(cls) -> None:
        """Fully quits the mixer to release resources."""
        if cls._initialized:
            cls.stop()
            try:
                pygame.mixer.quit()
                cls._initialized = False
                logger.info("Audio mixer quit successfully.")
            except Exception as e:
                logger.warning(f"Error during audio cleanup: {e}")
