import logging

def advance_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    formate = logging.Formatter('%(asctime)s : %(process)d : %(levelname)s : %(message)s')


    fh = logging.FileHandler("myapp.txt")
    fh.setFormatter(formate)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(formate)
    logger.addHandler(sh)
    return(logger)

logger = advance_logger()
logger.info("hello thi is just a file")
