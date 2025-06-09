from speech_generation import Voice
from text_generation import Chat
from static_ffmpeg import run
from io import BytesIO
import re
import asyncio
import json
from typing import Dict, List, Set
import json
import discord
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
discord_token = config.get("discord_token")
openai_token = config.get("openai_token")
elevenlabs_token = config.get("elevenlabs_token")
model_default = config.get("model_default", None)
model_list = config.get("model_list", None)
# Config Items that can be None
guild_id = config.get("guild_id", None)
category_id = config.get("category_id", None)
admin_user_id = config.get("admin_user_id", None)
allowed_tools = config.get("allowed_tools", None)
allowed_choices = config.get("allowed_tool_choice", None)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
chatgpt = Chat(openai_token, model_default)
elevenlabs = Voice(elevenlabs_token)


@client.event
async def on_ready():
    bot_logger.info(f'We have logged in as {client.user}')


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
        try:
            # generate ChatGPT prompt
            channel_config = await get_channel_config(message.channel)

            history_parameter_list = ['image_count_max', 'history_length']
            generation_parameter_list = [
                'model_version', 'temperature', 'tools', 'tool_choice']

            history_parameters = dict()
            generation_parameters = dict()

            history_parameters = {key: channel_config.get(
                key, None) if channel_config is not None else None for key in history_parameter_list}

            message_history = await generate_messagehistory(
                channel=message.channel, **history_parameters)

            system_message = channel_config.get(
                "system_message", None) if channel_config is not None else None

            if system_message is not None:
                if channel_config.get("sys_msg_order", None) == "first":
                    message_history.insert(
                        0, {"role": "system", "content": channel_config["system_message"]})
                else:
                    message_history.append(
                        {"role": "system", "content": channel_config["system_message"]})

            generation_parameters = {key: channel_config.get(
                key, None) if channel_config is not None else None for key in generation_parameter_list}

            response = await chatgpt.get_response_async(message_history, **generation_parameters)

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
    if 'response' in locals():
        await send_message_blocks(message.channel, response)


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    cross_reaction = "\u274c"
    exclamation_reaction = "\u203c"
    if (payload.emoji.name == cross_reaction) and \
            (admin_user_id is None or payload.user_id == int(admin_user_id)):
        deletion_messages_list: Set[discord.Message] = set()

        guild_channel = client.get_guild(
            payload.guild_id).get_channel(payload.channel_id)
        admin_user = None
        if admin_user_id is not None:
            admin_user = client.get_guild(
                payload.guild_id).get_member(int(admin_user_id))
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
            (admin_user_id is None or payload.user_id == int(admin_user_id)):
        pass
    else:
        bot_logger.debug("Reaction added")


async def send_message_blocks(channel: discord.TextChannel, content: str):
    remaining_content = content
    while len(remaining_content) > 2000:
        current_block = remaining_content[:2000]
        # check for codeblock then cut neatly on a line inside block while leaving space for closing brackets
        while len(current_block) > 1997 and current_block.count("```") % 2 > 0:
            current_block = current_block.rsplit(
                "\n", 1)[0]  # split on last new line
        if current_block.count("```") % 2 > 0:
            # gather language code if possible
            language_code = ""
            opening_bracket_index = current_block.rfind("```") + 3
            if opening_bracket_index > -1:
                language_code = current_block[opening_bracket_index:].split("\n")[
                    0].split(" ")[0]
            # add closing code brackets
            current_block = current_block + "```"
            # add opening brackets to remaining content
            remaining_content = "```" + language_code + \
                remaining_content[len(current_block) - 3:]
        # cut neatly on last period
        else:
            last_line = current_block.rindex("\n")
            last_period = current_block.rindex(". ") + 1  # include period
            # check what comes first - new line or period
            current_block = current_block[:max(last_line, last_period)]
            remaining_content = remaining_content[len(current_block):]
        bot_logger.info(
            f"Sending message {(content-remaining_content)/2000}/{content/2000}")
        await channel.send(current_block)
    await channel.send(remaining_content)


def ensure_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes"):
            return True
        elif value.lower() in ("false", "0", "no"):
            return False
    raise ValueError(
        f"{value} is not a boolean or a recognizable string boolean")


async def get_channel_config(channel: discord.TextChannel):
    bot_logger.debug("Reading channel config from description")
    if channel.topic is None:
        return None
    # jsonify description
    description_json = dict()
    try:
        description_json = json.loads(channel.topic, strict=False)
    except Exception as e:
        bot_logger.error("Cannot parse channel status message", e)
        raise ValueError(f"Cannot parse channel status message", e)

    # check for model version
    if "model_version" in description_json:
        # check if model version is valid
        if description_json["model_version"] not in model_list:
            model_list_str = ", ".join(model_list)
            raise ValueError("Error channel_config model_version",
                             f"Invalid model version: {description_json['model_version']}.\nAllowed values: {model_list_str}")
        bot_logger.debug(
            f"Using model version: {description_json['model_version']}")

    # check for message history length
    if "history_length" in description_json:
        # check if history length is valid
        if description_json["history_length"] == 0:
            description_json["history_length"] = None
        elif description_json["history_length"] not in range(1, 100):
            raise ValueError("Error channel_config history_length",
                             f"Invalid history length: {description_json['history_length']}.\nAllowed values: 1-99, 0 for unlimited")
        bot_logger.debug(
            f"Using history length: {description_json['history_length']}")

    # check for image count max
    if "image_count_max" in description_json:
        # check if image count max is valid
        if description_json["image_count_max"] == 0:
            description_json["image_count_max"] = None
        elif description_json["image_count_max"] not in range(1, 100):
            raise ValueError("Error channel_config image_count_max",
                             f"Invalid image count max: {description_json['image_count_max']}.\nAllowed values: 1-99, 0 for unlimited")
        bot_logger.debug(
            f"Using image count max: {description_json['image_count_max']}")

    # check for system message
    if "system_message" in description_json:
        bot_logger.debug(
            f"Using system message: {description_json['system_message']}")

    # check for system message order
    if "sys_msg_order" in description_json:
        bot_logger.debug(
            f"Using system message order: {description_json['sys_msg_order']}")

    # check if voice enabled
    if "voice" in description_json:
        description_json["voice"] = ensure_bool(description_json["voice"])

    if "tools" in description_json:
        # Currently only handles built-in tools
        if isinstance(description_json["tools"], list) and set(description_json["tools"]).issubset(allowed_tools):
            tool_list = list()
            for tool in description_json["tools"]:
                tool_list.append({"type": tool})
            description_json["tools"] = tool_list # converted to built-in tool
        else:
            raise ValueError("Error channel_config tools",
                             f"Invalid set of tools specified: {description_json["tools"]}.\nAllowed options: {allowed_tools}")
        bot_logger.debug(f"Using tools: {description_json["tools"]}")

    if "tool_choice" in description_json:
        if description_json["tool_choice"] not in allowed_choices:
            raise ValueError("Error channel_config tool_choice",
                             f"Invalid tool choice: {description_json["tool_choice"]}.\nAllowed options: {allowed_choices}")
        bot_logger.debug(
            f"Using tool_choice: {description_json["tool_choice"]}")

    return description_json


async def generate_messagehistory(channel: discord.TextChannel, history_length: int = None, image_count_max: int = None):
    bot_logger.debug("Reading message history")
    message_history: List[Dict] = []
    previous_author = 0
    image_count = 0
    async for message in channel.history(limit=history_length):
        # ignore messages starting with !! or too short
        if message.content.startswith("!!") or len(message.content) < 2:
            continue
        # fetch message username
        message_user = None
        if message.author is not client.user:
            message_user = message.author.display_name.strip().replace(" ", "")
        # check if message contains image
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
                    {"type": "text", "text": message_content_without_url},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
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
            # check user or bot
            if message.author.id == client.user.id:
                message_history.append(
                    {"role": "assistant", "content": message.content})
            else:
                # check system message
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
            guild_id is not None and message.guild.id != int(guild_id):
        bot_logger.debug(f"Wrong or no guild")
        return True
    if message.channel.category is None or \
            category_id is not None and message.channel.category.id != int(category_id):
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
    client.run(discord_token)
