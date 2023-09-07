from io import BytesIO
import os
import re
import json
from typing import Set
from dotenv import load_dotenv
import discord

from text_generation import Chat
from speech_generation import Voice

load_dotenv()

discord_token = os.getenv("discord_token")
openai_token = os.getenv("openai_token")
elevenlabs_token = os.getenv("elevenlabs_token")
guild_id = os.getenv("guild_id")
category_id = os.getenv("category_id")
admin_user_id = os.getenv("admin_user_id")
model_version = os.getenv("model_version")

if model_version is None or model_version == "":
    model_version = "gpt-4"
print(f"Now using {model_version}")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
chatgpt = Chat(openai_token, model_version)
elevenlabs = Voice(elevenlabs_token)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message: discord.Message):
    if ignore_message(message):
        print("Not my business")
        return

    print("Working...")
    async with message.channel.typing():
        try:
            # generate ChatGPT prompt
            channel_config = await get_channel_config(message.channel)
            if channel_config is not None:
                # generate history
                if "history_length" in channel_config:
                    message_history = await generate_messagehistory(
                        message.channel, channel_config["history_length"])
                else:
                    message_history = await generate_messagehistory(
                        message.channel)

                # add system message if available
                if "system_message" in channel_config:
                    message_history.append(
                        {"role": "system", "content": channel_config["system_message"]})

                # generate response
                if "model_version" in channel_config:
                    response = await chatgpt.get_response_async(
                        message_history, channel_config["model_version"])
                else:
                    response = await chatgpt.get_response_async(message_history)
            else:
                message_history = await generate_messagehistory(message.channel)
                response = await chatgpt.get_response_async(message_history)

            # check if user is in voice -> generate TTS if funds available
            if message.author.voice and message.author.voice.channel:
                voice_client = await message.author.voice.channel.connect()
                try:
                    if elevenlabs.get_character_remaining() > len(response):
                        text_bytes = elevenlabs.get_voice_bytes(response)
                        text_bytes_io = BytesIO(text_bytes)
                        voice_client.play(discord.FFmpegPCMAudio(
                            text_bytes_io, pipe=True))
                        elevenlabs.remove_history(response)
                    else:
                        # say not enough funds
                        voice_client.play(discord.FFmpegPCMAudio(
                            "not_enough_tokens.mp3", pipe=True))
                    while voice_client.is_playing():
                        pass
                except Exception as e:
                    error_embed = discord.Embed(
                        title="Error playing voice", description=f"```{str(e)}```", color=discord.Color.red())
                    await message.channel.send(embed=error_embed)
                await voice_client.disconnect()
        except Exception as e:
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
            print(f"Deleted {len(deletion_messages_list)} messages!")
    elif (payload.emoji.name == exclamation_reaction) and \
            (admin_user_id is None or payload.user_id == int(admin_user_id)):
        pass
    else:
        print("Reaction added")


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
        await channel.send(current_block)
    await channel.send(remaining_content)


async def get_channel_config(channel: discord.TextChannel):
    print("Reading channel config from description")
    if channel.topic is None:
        return None
    try:
        # jsonify description
        description_json = json.loads(channel.topic)

        channel_config = {}
        # check for model version
        if "model_version" in description_json:
            # check if model version is valid
            if description_json["model_version"] in ["davinci", "gpt-3.5-turbo", "gpt-4"]:
                channel_config["model_version"] = description_json["model_version"]
            else:
                error_embed = discord.Embed(
                    title="Error channel_config model_version", description=f"Invalid model version: {description_json['model_version']}.\n" +
                    "Allowed values: davinci, gpt-3.5-turbo, gpt-4", color=discord.Color.red())
                await channel.send(embed=error_embed)
            print(f"Using model version: {channel_config['model_version']}")

        # check for message history length
        if "history_length" in description_json:
            # check if history length is valid
            if description_json["history_length"] == 0:
                channel_config["history_length"] = None
            elif description_json["history_length"] in range(1, 100):
                channel_config["history_length"] = description_json["history_length"]
            else:
                error_embed = discord.Embed(
                    title="Error channel_config history_length", description=f"Invalid history length: {description_json['history_length']}.\n" +
                          "Allowed values: 1-99, 0 for unlimited", color=discord.Color.red())
                await channel.send(embed=error_embed)
            print(f"Using history length: {channel_config['history_length']}")

        # check for system message
        if "system_message" in description_json:
            channel_config["system_message"] = description_json["system_message"]

        return channel_config
    except Exception as e:
        error_embed = discord.Embed(
            title="Error channel_config", description=f"```{str(e)}```", color=discord.Color.red())
        await channel.send(embed=error_embed)
        print(f"Error reading description: {e}")
    return None


async def generate_messagehistory(channel: discord.TextChannel, history_length: int = None):
    print("Reading message history")
    message_history = []
    previous_author = 0
    async for message in channel.history(limit=history_length):
        # ignore messages starting with !! or too short
        if message.content.startswith("!!") or len(message.content) < 2:
            continue
        # combine adjacent messages from same author
        if len(message_history) > 0 and \
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

    # reverse message history
    message_history.reverse()
    return message_history


def ignore_message(message: discord.Message) -> bool:
    '''Checks for bot account,
    chat inside certain guild with category,
    aswell as system prompt'''
    if message.content.startswith("!!"):
        print("Ignore specified")
        return True
    if message.author.bot or message.author.id == client.user.id:
        print("Bot detected")
        return True
    if message.guild is None or \
            guild_id is not None and message.guild.id != int(guild_id):
        print(f"Wrong or no guild")
        return True
    if message.channel.category is None or \
            category_id is not None and message.channel.category.id != int(category_id):
        print("Not in Category")
        return True
    if message.content.startswith('{') and message.content.endswith("}"):
        print("System message")
        return True
    if len(message.content) < 2:
        print("Empty message")
        return True
    return False


client.run(discord_token)
