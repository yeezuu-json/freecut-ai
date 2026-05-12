from dotenv import load_dotenv

from app.application import run_app

if __name__ == "__main__":
    load_dotenv()
    run_app()