from elevenlabs.client import ElevenLabs
from logging import getLogger

voice_logger = getLogger(__name__)


class Voice:
    def __init__(self, token: str, name: str = "Glinda") -> None:
        self.__api_key = token
        self.__client = ElevenLabs(api_key=self.__api_key)
        self.__voice_name = name

    def get_voice_bytes(self, prompt: str) -> bytes:
        remaining = self.get_character_remaining()
        if remaining >= len(prompt):
            voice_logger.debug("Fetching audio from ElevenLabs")
            voice_logger.debug(
                f"Using {len(prompt)} characters out of {remaining} remaining.")
            audio_bytes = self.__client.generate(
                prompt, voice=self.__voice_name)
            voice_logger.debug(
                f"Remaining characters: {self.get_character_remaining()}")
            return audio_bytes
        else:
            voice_logger.warning("You do not have enough characters left this month for this voice.",
                                 f"(Needed: {len(prompt)} / Remaining: {remaining})")
        raise Exception("Unable to generate voice")

    def get_voice_bytes_history(self, prompt: str) -> bytes:
        client = ElevenLabs(api_key=self.__api_key)
        for historyItem in client.history.get_all().items:
            if historyItem.text == prompt:
                audio_bytes = historyItem.audio
                return audio_bytes
        raise Exception("Voice file not found")

    def remove_history(self, prompt: str) -> None:
        for historyItem in self.__client.history.get_all().items:
            if historyItem.text == prompt:
                historyItem.delete()
                voice_logger.debug("Successfully deleted voice")
                return
        raise Exception("Could not find voice")

    def get_character_remaining(self) -> int:
        subscription = self.__client.user.get_subscription()
        limit = subscription.character_limit
        current = subscription.character_count
        percentage = current / limit * 100
        voice_logger.info(
            f"Used up {current} out of {limit} characters ({percentage}%).")
        return limit - current
