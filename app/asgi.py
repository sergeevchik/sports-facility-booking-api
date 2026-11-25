import logging

from app.main import create_app

logging.basicConfig(level=logging.INFO, format="%(message)s")
app = create_app()
