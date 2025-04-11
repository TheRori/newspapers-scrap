# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os


is_subprocess = os.environ.get('SUBPROCESS_LOG') == '1'

# Use a different log file name for subprocesses
log_file = 'subprocess.log' if is_subprocess else 'application.log'

# Configure the log format
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Log to file
file_handler = RotatingFileHandler('app.log', maxBytes=1000000, backupCount=3)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

# Log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(
    'application.log',
    maxBytes=10485760,  # 10MB
    backupCount=5,
    encoding='utf-8'
)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Make sure all loggers propagate to root
# This ensures logs from all modules are captured
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).propagate = True

# Suppress werkzeug logs if needed
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)