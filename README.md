# Simple Discord bot to access ChatGPT written in Python

## Features

- Check for guild_id and category_id to only work in a specific "directory" (security reasons - I'm paranoid)
- Each Channel below a category is a conversation
- Messages encased in `{...}` are marked as System
- Messages starting with `!!` will be ignored
- Long messages will be split into 2000 characters
  - Code-Blocks will be split on linebreaks cleanly
  - Language-Code will be transferred if available
  - Normal messages will be split on last period or linebreak

## Ressources

- [ChatGPT](chat.openai.com)
- [ChatGPT API](https://platform.openai.com/docs/api-reference)
- [Discord.py](https://discordpy.readthedocs.io/en/stable/)
