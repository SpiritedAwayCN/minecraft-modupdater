import logging

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Create formatter (include file and line number)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(filename)s:%(lineno)d - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    

    # Add formatter to ch
    ch.setFormatter(formatter)

    # Add ch to logger
    logger.addHandler(ch)

    return logger