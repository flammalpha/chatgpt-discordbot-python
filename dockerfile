FROM python:3.11-slim

ARG openai_token
ARG elevenlabs_token
ARG discord_token

# ensure debian
RUN apt-get update && apt-get install -y ffmpeg

# ensure python
COPY . .
RUN pip install -r requirements.txt

# run bot
CMD ["python", "bot.py"]
