# import logging

# import logtail

# logger = logging.getLogger("pytorch-model")
# logger.setLevel(logging.INFO)

# logtail_handler = logtail.LogtailHandler(
#     source_token="change-me-before-production",
#     host="localhost:8000",
# )
# logtail_handler.setFormatter(
#     logging.Formatter(
#         "[%(levelname)s]: %(message)s"
#     )
# )
# logger.addHandler(logtail_handler)