from elevenlabslib import ElevenLabsUser


class Voice:
    name = "Bella"

    def __init__(self, token) -> None:
        self.__eleven_labs_user = ElevenLabsUser(token)
        self.__eleven_labs_voice = self.__eleven_labs_user.get_voices_by_name(self.name)[
            0]

    def get_voice_bytes(self, prompt: str) -> bytes:
        remaining = self.get_character_remaining()
        if remaining >= len(prompt):
            print("Fetching audio from ElevenLabs")
            print(
                f"Using {len(prompt)} characters out of {remaining} remaining.")
            audio_bytes = self.__eleven_labs_voice.generate_audio_bytes(prompt)
            print(
                f"Remaining characters: {self.get_character_remaining()}")
            return audio_bytes
        else:
            print("You do not have enough characters left this month for this voice.")
            print(f"(Needed: {len(prompt)} / Remaining: {remaining})")
        raise Exception("Unable to generate voice")

    def get_voice_bytes_history(self, prompt: str) -> bytes:
        for historyItem in self.__eleven_labs_user.get_history_items():
            if historyItem.text == prompt:
                audio_bytes = historyItem.get_audio_bytes()
                return audio_bytes
        raise Exception("Voice file not found")

    def remove_history(self, prompt: str) -> None:
        for historyItem in self.__eleven_labs_user.get_history_items():
            if historyItem.text == prompt:
                historyItem.delete()
                print("Successfully deleted voice")
                return
        raise Exception("Could not find voice")

    def get_character_remaining(self) -> int:
        limit = self.__eleven_labs_user.get_character_limit()
        current = self.__eleven_labs_user.get_current_character_count()
        print(f"Used up {current} out of {limit} characters.")
        return limit - current
