import logging
from logging.handlers import TimedRotatingFileHandler


def setup_logger(log_file: str = "bot.py", log_level = logging.DEBUG):
    logger = logging.getLogger()
    logger.setLevel(level=log_level)

    if not logger.handlers:
        stream_logger = logging.StreamHandler()
        stream_logger.setLevel(logging.INFO)
        stream_logger.setFormatter('%(asctime)s [%(levelname)s] %(message)s')

        file_logger = TimedRotatingFileHandler(
            'logs/bot.log',
            when="midnight",
            interval=1,
            backupCount=50 # keep 50 files
        )
        file_logger.suffix = "%Y-%m-%d"
        file_logger.setLevel(logging.DEBUG)
        file_logger.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

        logger.addHandler(stream_logger)
        logger.addHandler(file_logger)

if __name__ == "__main__":
    setup_logger()