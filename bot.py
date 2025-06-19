import base64
import math
import os
from speech_generation import Voice
from text_generation import Chat
from static_ffmpeg import run
from io import BytesIO
import re
import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set, TypedDict
import json
import discord
from discord.ext import commands
from logging import getLogger
from logging_config import setup_logger

setup_logger()

bot_logger = getLogger(__name__)

# testing
# import importlib
# import test_message


with open('config.json', 'r') as config_file:
    config: Dict = json.load(config_file)

# Config Items that never should be None
COMMAND_PREFIX = config.get("command_prefix", "!")
DISCORD_TOKEN = config.get("discord_token")
OPENAI_TOKEN = config.get("openai_token")
ELEVENLABS_TOKEN = config.get("elevenlabs_token")
MODEL_DEFAULT = config.get("model_default", None)
MODEL_LIST = config.get("model_list", None)
# Config Items that can be None
GUILD_ID = config.get("guild_id", None)
CATEGORY_ID = config.get("category_id", None)
ADMIN_USER_ID = config.get("admin_user_id", None)
ALLOWED_TOOLS = config.get("allowed_tools", None)
ALLOWED_CHOICES = config.get("allowed_tool_choice", None)
# General items that normally won't be defined
MAX_HISTORY_LENGTH = config.get("max_history_length", 100)
MAX_IMAGE_COUNT = config.get("max_image_count", 100)
# Constants
MAX_MESSAGE_SIZE = 2000  # Discord message length maximum


class CustomParameter(TypedDict):
    name: str
    description: str
    category: str
    type: type
    validator: Optional[Callable]
    options: Optional[List[str]]


PARAMETER_LIST: List[CustomParameter] = [
    {
        'name': 'image_count_max',
        'description': "Amount of pictures to include in history (sending towards OpenAI).",
        'category': "history",
        'type': int,
        'validator': lambda v: 0 <= v < 100,
    },
    {
        'name': 'history_length',
        'description': "Amount of messages to include in history (sending towards OpenAI).",
        'category': "history",
        'type': int,
        'validator': lambda v: 0 <= v < 100,
    },
    {
        'name': 'system_message',
        'description': "Permanent system message the AI should adhere to (max 1000 characters).",
        'category': "history",
        'type': str,
        'validator': lambda v: len(v) < 1000,
    },
    {
        'name': 'sys_msg_order',
        'description': "Weather the system message should be added as first or last message (Default last).",
        'category': "history",
        'type': str,
        'options': ["first", "last"],
    },
    {
        'name': 'model_version',
        'description': "Model name for OpenAI (e.g. gpt-4.1).",
        'category': "generation",
        'type': str,
        'options': MODEL_LIST,
    },
    {
        'name': 'temperature',
        'description': "Amount of fuzzyness the response should have (0.0=None, 1.0=Default, 2.0=Crazy).",
        'category': "generation",
        'type': float,
        'validator': lambda v: 0.0 <= v <= 2.0,
    },
    {
        'name': 'tools',
        'description': "Tools to include in response generation (e.g. image_generation).",
        'category': "generation",
        'type': str,
        'options': ALLOWED_TOOLS,
    },
    {
        'name': 'tool_choice',
        'description': "How the model should decide to use tools (default none).",
        'category': "generation",
        'type': str,
        'options': ALLOWED_CHOICES,
    },
    {
        'name': 'voice',
        'description': "If the bot should be able to respond in voice channel from this chat.",
        'category': 'bot',
        'type': bool,
    }
]


intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
chatgpt = Chat(OPENAI_TOKEN, MODEL_DEFAULT)
elevenlabs = Voice(ELEVENLABS_TOKEN)


@client.tree.command()
async def kill(context: discord.Interaction):
    """Force stop the bot."""
    await context.response.send_message("Shutting down...", ephemeral=True)
    bot_logger.info("Bot is shutting down, requested"
                    f" by user {context.user.name} ({context.user.id})"
                    f" in guild {context.guild.name} ({context.guild.id})"
                    f" in channel {context.channel.name} ({context.channel.id})")
    try:
        await asyncio.wait_for(client.close(), timeout=5)
        bot_logger.info("Bot has shut down gracefully")
    except asyncio.TimeoutError:
        bot_logger.warning(
            "Graceful shutdown timed out, force closing connections")
        os._exit(0)


@client.tree.command(name="config", description="Set a configuration option for the current channel.")
@discord.app_commands.describe(
    option="The configuration option to set",
    value="The value to set for the configuration option"
)
@discord.app_commands.choices(
    option=[
        discord.app_commands.Choice(name=opt["name"], value=opt["name"])
        for opt in PARAMETER_LIST
    ]
)
async def config(
    interaction: discord.Interaction,
    option: discord.app_commands.Choice[str],
    value: str
):
    """Set a configuration option for the current channel."""
    # await interaction.response.defer()
    config_option = get_config_option(option.value)
    if not config_option:
        return await interaction.response.send_message(f"Unknown option: {option.value}", ephemeral=True)

    expected_type = config_option["type"]
    try:
        if expected_type is bool:
            cast_value = ensure_bool(value)
        elif expected_type is int:
            cast_value = int(value)
        elif expected_type is float:
            cast_value = float(value)
        elif expected_type is str:
            cast_value = str(value)
        else:
            return await interaction.response.send_message(
                f"Unsupported type for {option.value}: {expected_type.__name__}", ephemeral=True
            )
    except Exception:
        return await interaction.response.send_message(
            f"Value for {option.value} must be of type {expected_type.__name__}", ephemeral=True
        )

    if config_option.get("validator"):
        valid, msg = config_option["validator"](cast_value)
        if not valid:
            return await interaction.response.send_message(
                f"Validation failed: {msg}", ephemeral=True
            )

    await set_channel_config(interaction.channel, option.value, cast_value)
    bot_logger.info(
        f"Setting {option.value} to {cast_value} in channel {interaction.channel.name}")

    await interaction.response.send_message(
        f"Set `{option.value}` to `{cast_value}`!", ephemeral=True
    )


@config.autocomplete("value")
async def config_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    """Provide autocomplete suggestions for configuration parameter."""
    selected_option = interaction.data.get("options", [{}])[0].get("value")
    if not selected_option:
        return [discord.app_commands.Choice(name="Select an option", value="")]

    config_option = get_config_option(selected_option)
    if not config_option:
        return [discord.app_commands.Choice(name="Unknown option", value="")]
    if config_option.get("options"):
        available_options = [
            discord.app_commands.Choice(name=opt, value=opt)
            for opt in config_option["options"]
            if current.lower() in opt.lower()
        ]
        return available_options[:25]  # Limit to 25 choices
    else:
        # If the option is a boolean, provide True/False choices
        if config_option["type"] is bool:
            return [
                discord.app_commands.Choice(name="True", value="True"),
                discord.app_commands.Choice(name="False", value="False")
            ]
    return []


@config.error
async def config_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Handle errors for the config command."""
    bot_logger.error(f"Error in config command: {error}", exc_info=True)
    if isinstance(error, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True)
    elif isinstance(error, discord.app_commands.errors.CommandInvokeError):
        await interaction.response.send_message(
            f"An error occurred while setting the configuration: {str(error)}", ephemeral=True)
    elif isinstance(error, discord.app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(
            f"This command is on cooldown. Please try again later.", ephemeral=True)
    else:
        await interaction.response.send_message(
            f"An unexpected error occurred: {str(error)}", ephemeral=True)


@client.event
async def on_ready():
    bot_logger.info(f'We have logged in as {client.user}')
    await client.tree.sync()
    bot_logger.info(f'Synced all commands')


@client.event
async def on_message(message: discord.Message):
    # if message.guild is None and message.author.id != client.user.id:
    #     if message.content.startswith("??"):
    #         # update function
    #         importlib.reload(test_message)
    #         await message.channel.send("Reloaded")
    #     else:
    #         await test_message.handle_test_message(message)
    #     return
    if ignore_message(message):
        bot_logger.debug("Not my business")
        return

    bot_logger.debug("Working...")
    async with message.channel.typing():
        response = None
        images = None
        try:
            # generate ChatGPT prompt
            channel_config = await check_channel_config(message.channel)

            history_parameters = dict()
            generation_parameters = dict()

            history_parameters = {key: channel_config.get(
                key, None) if channel_config is not None else None
                for key in
                [key["name"] for key in PARAMETER_LIST if key["category"] == "history"]}

            message_history = await generate_messagehistory(
                channel=message.channel, **history_parameters)

            generation_parameters = {key: channel_config.get(
                key, None) if channel_config is not None else None
                for key in
                [key["name"] for key in PARAMETER_LIST if key["category"] == "generation"]}

            response, images = await chatgpt.get_response_async(message_history, **generation_parameters)

            # check if user is in voice -> generate TTS if funds available
            if channel_config is not None and \
                    "voice" in channel_config and channel_config["voice"] and \
                    message.author.voice and message.author.voice.channel:
                voice_client = await message.author.voice.channel.connect()
                try:
                    if elevenlabs.get_character_remaining() > len(response):
                        text_bytes = elevenlabs.get_voice_bytes(response)
                        text_bytes_io = BytesIO(text_bytes)
                        ffmpeg, ffprobe = run.get_or_fetch_platform_executables_else_raise()
                        voice_client.play(discord.FFmpegPCMAudio(
                            text_bytes_io, executable=ffmpeg, pipe=True))
                        while voice_client.is_playing():
                            await asyncio.sleep(1)
                        elevenlabs.remove_history(response)
                    else:
                        # say not enough funds
                        voice_client.play(discord.FFmpegPCMAudio(
                            "not_enough_tokens.mp3", pipe=True))
                    while voice_client.is_playing():
                        pass
                except Exception as e:
                    bot_logger.error("Cannot play voice", e)
                    error_embed = discord.Embed(
                        title="Error playing voice", description=f"```{str(e)}```", color=discord.Color.red())
                    await message.channel.send(embed=error_embed)
                await voice_client.disconnect()
        except Exception as e:
            bot_logger.error("Cannot generate message", e)
            error_embed = discord.Embed(
                title="Error on_message", description=f"```{str(e)}```", color=discord.Color.red())
            await message.channel.send(embed=error_embed)
    if response is not None:
        await send_message_blocks(message.channel, response)
    if images is not None and len(images) > 0:
        await send_images(message.channel, images)


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    cross_reaction = "\u274c"
    exclamation_reaction = "\u203c"
    if (payload.emoji.name == cross_reaction) and \
            (ADMIN_USER_ID is None or payload.user_id == int(ADMIN_USER_ID)):
        deletion_messages_list: Set[discord.Message] = set()

        guild_channel = client.get_guild(
            payload.guild_id).get_channel(payload.channel_id)
        admin_user = None
        if ADMIN_USER_ID is not None:
            admin_user = client.get_guild(
                payload.guild_id).get_member(int(ADMIN_USER_ID))
        # reacted_message = await guild_channel.fetch_message(payload.message_id)
        # Get message history to check for multiple reactions
        async for message in guild_channel.history(limit=None, oldest_first=True):
            for reaction in message.reactions:
                if reaction.emoji == cross_reaction and \
                        (admin_user is None or admin_user in await reaction.users()):
                    deletion_messages_list.add(message)
        # if two reactions with :X: exist -> delete all messages inbetween
        if len(deletion_messages_list) % 2 == 0:
            deleting = False
            async for message in guild_channel.history(limit=None, oldest_first=True):
                for reaction in message.reactions:
                    if reaction.emoji == cross_reaction and \
                            (admin_user is None or admin_user in await reaction.users()):
                        deleting = not deleting
                if deleting:
                    deletion_messages_list.add(message)
            await guild_channel.delete_messages(deletion_messages_list)
            bot_logger.info(f"Deleted {len(deletion_messages_list)} messages!")
    elif (payload.emoji.name == exclamation_reaction) and \
            (ADMIN_USER_ID is None or payload.user_id == int(ADMIN_USER_ID)):
        pass
    else:
        bot_logger.debug("Reaction added")


async def send_message_blocks(channel: discord.TextChannel, content: str):
    remaining_content = content
    while len(remaining_content) > MAX_MESSAGE_SIZE:
        current_block = remaining_content[:MAX_MESSAGE_SIZE]
        # check for codeblock then cut neatly on a line inside block while leaving space for closing brackets
        while len(current_block) > 1997 and current_block.count("```") % 2 > 0:
            current_block = current_block.rsplit(
                "\n", 1)[0]  # split on last new line
        if current_block.count("```") % 2 > 0:
            language_code = ""
            opening_bracket_index = current_block.rfind("```") + 3
            if opening_bracket_index > -1:
                language_code = current_block[opening_bracket_index:].split("\n")[
                    0].split(" ")[0]
            current_block = current_block + "```"
            remaining_content = "```" + language_code + \
                remaining_content[len(current_block) - 3:]
        # cut neatly on last period
        else:
            last_line = current_block.rfind("\n")
            last_period = current_block.rfind(
                ". ") + (1 if ". " in current_block else 0)
            cutoff_index = max(last_line, last_period)
            if cutoff_index < 1500:  # somehow last period and new-line are more than 500 characters behind? reduce message waste
                last_space = current_block.rfind(" ")
                cutoff_index = max(last_space, cutoff_index)
            current_block = current_block[:cutoff_index]
            remaining_content = remaining_content[len(current_block):]
        bot_logger.info(f"Sending message {(math.ceil(len(content)-len(remaining_content))/MAX_MESSAGE_SIZE)}"
                        f"/{math.ceil(len(content)/MAX_MESSAGE_SIZE)}")
        await channel.send(current_block)
    await channel.send(remaining_content)


async def send_images(channel: discord.TextChannel, images: List):
    for image in images:
        image_data = base64.b64decode(image)
        image_bytes = BytesIO(image_data)
        image_bytes.seek(0)

        discord_file = discord.File(fp=image_bytes, filename="image.png")
        await channel.send(file=discord_file)


def ensure_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes", "on", "enabled", "active", "y"):
            return True
        elif value.lower() in ("false", "0", "no", "off", "disabled", "inactive", "n"):
            return False
    raise ValueError(
        f"{value} is not a boolean or a recognizable string boolean")


async def fetch_channel_config(channel: discord.TextChannel) -> Optional[dict]:
    """Fetches the channel configuration from the channel topic."""
    bot_logger.debug("Fetching channel config from topic")
    if channel.topic is None:
        return None
    topic_json = dict()
    try:
        topic_json = json.loads(channel.topic, strict=False)
    except Exception as e:
        bot_logger.error("Cannot parse channel topic message", e)
        raise ValueError(f"Cannot parse channel topic message", e)

    return topic_json


async def check_channel_config(channel: discord.TextChannel) -> dict:
    bot_logger.debug("Checking channel config from description")

    description_json = await fetch_channel_config(channel)
    if description_json is None:
        bot_logger.debug("No channel config found, using defaults")
        return None

    if "model_version" in description_json:
        if description_json["model_version"] not in MODEL_LIST:
            model_list_str = ", ".join(MODEL_LIST)
            raise ValueError("Error channel_config model_version",
                             f"Invalid model version: {description_json['model_version']}."
                             f"\nAllowed values: {model_list_str}")
        bot_logger.debug(
            f"Using model version: {description_json['model_version']}")

    if "history_length" in description_json:
        if description_json["history_length"] == 0:
            description_json["history_length"] = None
        elif description_json["history_length"] not in range(1, MAX_HISTORY_LENGTH):
            raise ValueError("Error channel_config history_length",
                             f"Invalid history length: {description_json['history_length']}."
                             f"\nAllowed values: 1-99, 0 for unlimited")
        bot_logger.debug(
            f"Using history length: {description_json['history_length']}")

    if "image_count_max" in description_json:
        if description_json["image_count_max"] == 0:
            description_json["image_count_max"] = None
        elif description_json["image_count_max"] not in range(1, MAX_IMAGE_COUNT):
            raise ValueError("Error channel_config image_count_max",
                             f"Invalid image count max: {description_json['image_count_max']}."
                             f"\nAllowed values: 1-99, 0 for unlimited")
        bot_logger.debug(
            f"Using image count max: {description_json['image_count_max']}")

    if "system_message" in description_json:
        bot_logger.debug(
            f"Using system message: {description_json['system_message']}")

    if "sys_msg_order" in description_json:
        bot_logger.debug(
            f"Using system message order: {description_json['sys_msg_order']}")

    if "voice" in description_json:
        description_json["voice"] = ensure_bool(description_json["voice"])

    if "tools" in description_json:
        # Currently only handles built-in tools
        if isinstance(description_json["tools"], list) and set(description_json["tools"]).issubset(ALLOWED_TOOLS):
            tool_list = list()
            for tool in description_json["tools"]:
                tool_list.append({"type": tool})
            description_json["tools"] = tool_list  # converted to built-in tool
        else:
            raise ValueError("Error channel_config tools",
                             f"Invalid set of tools specified: {description_json['tools']}."
                             f"\nAllowed options: {ALLOWED_TOOLS}")
        bot_logger.debug(f"Using tools: {description_json['tools']}")

    if "tool_choice" in description_json:
        if description_json["tool_choice"] not in ALLOWED_CHOICES:
            raise ValueError("Error channel_config tool_choice",
                             f"Invalid tool choice: {description_json['tool_choice']}."
                             f"\nAllowed options: {ALLOWED_CHOICES}")
        bot_logger.debug(
            f"Using tool_choice: {description_json['tool_choice']}")

    return description_json


async def set_channel_config(channel: discord.TextChannel, key: str, value: Any) -> None:
    '''Sets a channel config item in the channel topic'''
    original_config = await fetch_channel_config(channel)
    if original_config is None:
        original_config = {}
    if value is None:
        if key in original_config:
            del original_config[key]
    else:
        original_config[key] = value

    channel_topic = json.dumps(original_config, ensure_ascii=False)
    try:
        bot_logger.debug(f"Setting channel topic to: {channel_topic}")
        await channel.edit(topic=channel_topic)
    except discord.Forbidden:
        bot_logger.error("Cannot edit channel topic, missing permissions")
        raise PermissionError("Cannot edit channel topic, missing permissions")


def get_config_option(name: str):
    for option in PARAMETER_LIST:
        if option["name"] == name:
            return option
    return None


async def generate_messagehistory(channel: discord.TextChannel, system_message: str = None, sys_msg_order: str = None, history_length: int = None, image_count_max: int = None):
    bot_logger.debug("Reading message history")
    message_history: List[Dict] = []
    previous_author = 0
    image_count = 0
    async for message in channel.history(limit=history_length):
        if message.content.startswith("!!") or len(message.content) < 2:
            continue
        message_user = None
        if message.author is not client.user:
            message_user = message.author.display_name.strip().replace(" ", "")
        image_url_regex = r"https?://[^\s]+\.(jpg|jpeg|png|gif)"
        image_match = re.search(image_url_regex, message.content)
        if (len(message.attachments) > 0 or image_match) and (image_count_max is None or image_count < image_count_max):
            image_url = ""
            message_content_without_url = message.content
            if len(message.attachments) > 0:
                image_url = message.attachments[0].url  # .split("?")[0]
            else:
                image_url = image_match.group(0)
                message_content_without_url = message.content.replace(
                    image_url, "")
            bot_logger.debug(f"Adding Image to History: {image_url}")
            message_history.append({
                "role": "user",
                "content": [
                    {"type": "input_text", "text": message_content_without_url},
                    {"type": "input_image", "image_url": image_url}
                ]
            })
            image_count += 1
        # combine adjacent messages from same author
        elif len(message_history) > 0 and \
                previous_author == message.author.id:
            # check for codeblock
            if str(message_history[-1]["content"]).startswith("```") and \
                    message.content.endswith("```"):
                message_history[-1]["content"] = message.content[:-3] + \
                    "\n" + str(message_history[-1]
                               ["content"]).split("\n", 1)[1]
            else:
                message_history[-1]["content"] += message.content + \
                    "\n" + message_history[-1]["content"]
        # add new entry for different author
        else:
            if message.author.id == client.user.id:
                message_history.append(
                    {"role": "assistant", "content": message.content})
            else:
                if message.content.startswith('{') and message.content.endswith("}"):
                    message_history.append(
                        {"role": "system", "content": message.content[1:-1]})
                else:
                    message_history.append(
                        {"role": "user", "content": message.content})
        previous_author = message.author.id
        # if message_user is not None: # New Responses API does not allow names per message
        #     message_history[-1].update({"name": message_user})

    # reverse message history
    message_history.reverse()

    if system_message is not None:
        if sys_msg_order == "first":
            message_history.insert(
                0, {"role": "system", "content": system_message})
        else:
            message_history.append(
                {"role": "system", "content": system_message})

    return message_history


def ignore_message(message: discord.Message) -> bool:
    '''Checks for bot account,
    chat inside certain guild with category,
    aswell as system prompt'''
    if message.content.startswith("!!"):
        bot_logger.debug("Ignore specified")
        return True
    if message.author.bot or message.author.id == client.user.id:
        bot_logger.debug("Bot detected")
        return True
    if message.guild is None or \
            GUILD_ID is not None and message.guild.id != int(GUILD_ID):
        bot_logger.debug(f"Wrong or no guild")
        return True
    if message.channel.category is None or \
            CATEGORY_ID is not None and message.channel.category.id != int(CATEGORY_ID):
        bot_logger.debug("Not in Category")
        return True
    if message.content.startswith('{') and message.content.endswith("}"):
        bot_logger.debug("System message")
        return True
    if len(message.content) < 2:
        bot_logger.debug("Empty message")
        return True
    return False


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
