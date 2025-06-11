import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logger(log_file: str = "logs/bot.log", log_level=logging.DEBUG):
    logger = logging.getLogger()
    logger.setLevel(level=log_level)

    if not logger.handlers:
        stream_logger = logging.StreamHandler()
        stream_logger.setLevel(logging.INFO)
        stream_logger.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'))

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_logger = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=50  # keep 50 files
        )
        file_logger.suffix = "%Y-%m-%d"
        file_logger.setLevel(log_level)
        file_logger.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

        logger.addHandler(stream_logger)
        logger.addHandler(file_logger)


if __name__ == "__main__":
    setup_logger()
