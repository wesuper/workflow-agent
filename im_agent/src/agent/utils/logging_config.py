import logging
import sys

def setup_logging(log_level=logging.INFO):
    """Set up basic logging."""
    root = logging.getLogger()
    root.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

if __name__ == '__main__':
    setup_logging(logging.DEBUG)
    logging.debug("Logging is configured.")
    logging.info("Info message.")
    logging.warning("Warning message.")
    logging.error("Error message.")
