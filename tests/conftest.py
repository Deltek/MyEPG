import os

# Must be set before config.py is imported (it raises if BOT_TOKEN is missing)
os.environ.setdefault("BOT_TOKEN", "fake-token-for-tests")
os.environ.setdefault("ADMIN_USER_ID", "0")
