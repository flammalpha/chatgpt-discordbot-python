from elevenlabs.client import ElevenLabs

class Voice:
    def __init__(self, token: str, name: str = "Glinda") -> None:
        self.__api_key = token
        self.__client = ElevenLabs(api_key=self.__api_key)
        self.__voice_name = name

    def get_voice_bytes(self, prompt: str) -> bytes:
        remaining = self.get_character_remaining()
        if remaining >= len(prompt):
            print("Fetching audio from ElevenLabs")
            print(
                f"Using {len(prompt)} characters out of {remaining} remaining.")
            audio_bytes = self.__client.generate(prompt, voice=self.__voice_name)
            print(
                f"Remaining characters: {self.get_character_remaining()}")
            return audio_bytes
        else:
            print("You do not have enough characters left this month for this voice.")
            print(f"(Needed: {len(prompt)} / Remaining: {remaining})")
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
                print("Successfully deleted voice")
                return
        raise Exception("Could not find voice")

    def get_character_remaining(self) -> int:
        subscription = self.__client.user.get_subscription()
        limit = subscription.character_limit
        current = subscription.character_count
        percentage = current / limit * 100
        print(f"Used up {current} out of {limit} characters ({percentage}%).")
        return limit - current
