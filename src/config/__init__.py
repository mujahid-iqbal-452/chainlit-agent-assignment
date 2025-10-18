import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    BASE_URL = os.getenv("BASE_URL")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
    WEATHER_URL     = os.getenv("WEATHER_URL")

# WEATHER_API_KEY = os.getenv("OWM_KEY", "YOUR_FREE_OWM_KEY_HERE")  # ← add real key
# WEATHER_URL     = "https://api.openweathermap.org/data/2.5/weather"
                   