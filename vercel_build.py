import os
import subprocess
import sys


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set; skipping Django migrations for this deployment.")
        return

    print("DATABASE_URL is set; applying Django migrations...")
    subprocess.check_call([sys.executable, "manage.py", "migrate", "--noinput"])


if __name__ == "__main__":
    main()
