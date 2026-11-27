from openai import OpenAI
import traceback
import os
from dotenv import load_dotenv
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("OPENAI_API_KEY")
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"),timeout=30, max_retries=0)
    response = client.models.list()
    print("API connection successful",response)

except Exception as e:
    traceback.print_exc()

    print("Exception:", repr(e))
    print("Cause:", repr(e.__cause__))