import openai
import tiktoken


class Chat:
    def __init__(self, token: str) -> None:
        openai.api_key = token

    def get_response(self, message_history: dict) -> str:
        '''Fetches response from ChatGPT-3.5-Turbo with entire message history'''

        print("Fetching response from ChatGPT")
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", messages=message_history)

        response = completion.choices[0].message.content

        print(response)
        print(f"({len(response)})")
        return response

    def calculate_tokens(self, messages: dict) -> int:
        '''Calculates an estimate of the tokens used by message history'''
        counter = tiktoken.encoding_for_model("gpt-3.5-turbo")
        raise "Not implemented yet"
        for entry in messages:
            counter.count_tokens(entry.content)
        return counter.count
