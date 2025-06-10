from typing import List
from openai import AsyncOpenAI, OpenAI
import tiktoken
from logging import getLogger

text_logger = getLogger(__name__)


class Chat:
    def __init__(self, token: str, model_version: str) -> None:
        self.__api_key = token
        self.__client = OpenAI(api_key=self.__api_key)
        self.__async_client = AsyncOpenAI(api_key=self.__api_key)
        self.__model_version = model_version

    def get_completion(self, message_history: dict, model_version: str = None) -> str:
        '''Fetches response from ChatGPT with entire message history'''
        fetch_model_version = model_version if model_version is not None else self.__model_version

        text_logger.debug("Fetching response from ChatGPT")
        completion = self.__client.chat.completions.create(
            model=fetch_model_version, messages=message_history)

        response = completion.choices[0].message.content

        # text_logger.debug(response)
        text_logger.info(f"Response with {len(response)} characters")
        return response

    async def get_completion_async(self, message_history: dict, model_version: str = None, temperature: float = None) -> str:
        '''Fetches response from ChatGPT with entire message history'''
        fetch_model_version = model_version if model_version is not None else self.__model_version

        text_logger.debug("Fetching response from ChatGPT")
        completion = await self.__async_client.chat.completions.create(
            model=fetch_model_version, temperature=temperature,
            messages=message_history)

        response = completion.choices[0].message.content

        # text_logger.debug(response)
        text_logger.info(f"Response with {len(response)} characters")
        return response

    async def get_response_async(self, message_history: dict, model_version: str = None, temperature: float = None, tools: List = None, tool_choice: str = None) -> str:
        '''Fetches response from ChatGPT with entire message history'''
        fetch_model_version = model_version if model_version is not None else self.__model_version

        text_logger.debug("Fetching response from ChatGPT")
        response = await self.__async_client.responses.create(
            model=fetch_model_version, temperature=temperature,
            tools=tools, tool_choice=tool_choice,
            input=message_history
        )

        image_list: List = [
            output.result for output in response.output if output.type == "image_generation_call"]

        text_logger.info(
            f"Response with {len(response.output_text)} characters and {len(image_list) if image_list is not None else 0} images.")
        return response.output_text, image_list

    def get_model_list(self) -> List[str]:
        model_list = self.__client.models.list()._get_page_items()
        parsed_model_list: List[str] = list()
        for model in model_list:
            parsed_model_list.append(model.id)
        return parsed_model_list

    def calculate_tokens(self, messages: dict) -> int:
        '''Calculates an estimate of the tokens used by message history'''
        encoding = tiktoken.encoding_for_model(self.__model_version)
        tokens_per_message = 3
        tokens_per_name = 1
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens
