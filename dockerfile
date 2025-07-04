FROM python:3.13-slim

# ensure debian
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app

# ensure python
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# ensure files
COPY *.py .
COPY .env .env
COPY config.json config.json

# run bot
CMD ["python", "bot.py"]
