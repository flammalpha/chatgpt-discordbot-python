from elevenlabs import generate, set_api_key
from elevenlabs.api import History, User

class Voice:
    def __init__(self, token: str, name: str = "Glinda") -> None:
        set_api_key(token)
        self.__voice_name = name

    def get_voice_bytes(self, prompt: str) -> bytes:
        remaining = self.get_character_remaining()
        if remaining >= len(prompt):
            print("Fetching audio from ElevenLabs")
            print(
                f"Using {len(prompt)} characters out of {remaining} remaining.")
            audio_bytes = generate(prompt, voice=self.__voice_name)
            print(
                f"Remaining characters: {self.get_character_remaining()}")
            return audio_bytes
        else:
            print("You do not have enough characters left this month for this voice.")
            print(f"(Needed: {len(prompt)} / Remaining: {remaining})")
        raise Exception("Unable to generate voice")

    def get_voice_bytes_history(self, prompt: str) -> bytes:
        for historyItem in History.from_api().items:
            if historyItem.text == prompt:
                audio_bytes = historyItem.audio
                return audio_bytes
        raise Exception("Voice file not found")

    def remove_history(self, prompt: str) -> None:
        for historyItem in History.from_api().items:
            if historyItem.text == prompt:
                historyItem.delete()
                print("Successfully deleted voice")
                return
        raise Exception("Could not find voice")

    def get_character_remaining(self) -> int:
        user = User.from_api()
        limit = user.subscription.character_limit
        current = user.subscription.character_count
        percentage = current / limit * 100
        print(f"Used up {current} out of {limit} characters ({percentage}%).")
        return limit - current
