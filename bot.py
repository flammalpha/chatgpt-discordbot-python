import os
from dotenv import load_dotenv
import discord

from text_generation import Chat
from speech_generation import Voice

load_dotenv()

discord_token = os.getenv("discord_token")
openai_token = os.getenv("openai_token")
elevenlabs_token = os.getenv("elevenlabs_token")
guild_id = int(os.getenv("guild_id"))
category_id = int(os.getenv("category_id"))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
chatgpt = Chat(openai_token)
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
            message_history = await generate_messagehistory(message.channel)
            response = await chatgpt.get_response_async(message_history)

            # check if user is in voice -> generate TTS if funds available
            if message.author.voice and message.author.voice.channel:
                # message.author.voice.channel.connect()
                if elevenlabs.get_character_remaining() > response:
                    # generate voice
                    pass
                else:
                    # say not enough funds
                    pass
        except Exception as e:
            error_embed = discord.Embed(
                title="Error", description=f"```{str(e)}```", color=discord.Color.red())
            await message.channel.send(embed=error_embed)
    if response is not None:
        await send_message_blocks(message.channel, response)


async def send_message_blocks(channel: discord.TextChannel, content: str):
    remaining_content = content
    while len(remaining_content) > 2000:
        current_block = remaining_content[:1999]
        # check for codeblock then cut neatly on a line inside block
        if current_block.count("```") % 2 > 0:
            codeblock_start = current_block.rfind(
                "```")  # last opened codeblock
            # check if not first / opening bracket
            if current_block[:codeblock_start].rfind("```") == -1:
                codeblock_start = len(current_block) - 1
            while len(current_block) > 1996:  # leave space for closing brackets
                current_block = current_block[:codeblock_start].rsplit(
                    "\n", 1)[0]  # split on last new line

            # gather language code if possible
            opening_bracket_index = current_block.rfind("```") + 3
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
            last_period = current_block.rindex(".") + 1  # include period
            # check what comes first - new line or period
            current_block = current_block[:max(last_line, last_period)]
            remaining_content = remaining_content[len(current_block):]
        await channel.send(current_block)
    await channel.send(remaining_content)


async def generate_messagehistory(channel: discord.TextChannel):
    print("Reading message history")
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        # ignore messages starting with !!
        if message.content.startswith("!!"):
            continue
        # check user or bot
        if message.author.id == client.user.id:
            messages.append(
                {"role": "assistant", "content": message.content})
        else:
            # check system message
            if message.content.startswith('{') and message.content.endswith("}"):
                messages.append(
                    {"role": "system", "content": message.content[1:-1]})
            else:
                messages.append(
                    {"role": "user", "content": message.content})
    return messages


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
    if message.guild is None or message.guild.id != guild_id:
        print(f"Wrong guild {message.guild.id} but expected {guild_id}")
        return True
    if message.channel.category is None or message.channel.category.id != category_id:
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
