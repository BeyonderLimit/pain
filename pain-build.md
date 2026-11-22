# P.A.I.N. 1.1 Version
## Optimized version for Linux

```
import multiprocessing
import feedparser
import random
import datetime
import aiohttp
import asyncio
import os
import vlc
import yt_dlp
import random
from ollama import Client
import sounddevice as sd
import spacy
import signal
import sys
from icalendar import Calendar, Event
from duckduckgo_search import DDGS
from dimits import Dimits
import voice_recording

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Global variables
vlc_player = None

def clean_exit(signum, frame):
    print("\nCleaning up and exiting...")
    if vlc_player:
        vlc_player.stop()
    sd.stop()
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

def get_time_of_day():
    current_time = datetime.datetime.now()
    if current_time.hour < 12:
        return "morning"
    elif 12 <= current_time.hour < 18:
        return "afternoon"
    else:
        return "evening"

def get_date():
    return datetime.datetime.now().strftime("%A, %B %d, %Y")

def get_coordinates(location_name):
    coordinates = {
        "New Haven, CT": {"latitude": 41.3083, "longitude": -72.9279, "name": location_name},
    }
    return coordinates.get(location_name, {"latitude": 0, "longitude": 0, "name": location_name})

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

async def get_weather(location):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={location['latitude']}&longitude={location['longitude']}&current_weather=true&timezone=America/New_York"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if 'current_weather' in data:
                    weather = data['current_weather']
                    weather_code = weather.get('weathercode', 'unknown')
                    temp_celsius = weather.get('temperature', 'N/A')

                    if temp_celsius != 'N/A':
                        temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)

                        # Weather code descriptions
                        weather_descriptions = {
                            0: "Clear sky",
                            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                            45: "Fog", 48: "Depositing rime fog",
                            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                            77: "Snow grains",
                            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                            85: "Slight snow showers", 86: "Heavy snow showers",
                            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
                        }

                        weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")

                        return f"The current weather in {location['name']} is {weather_description} with a temperature of {temp_fahrenheit:.1f}°F."
                    else:
                        return "Could not retrieve temperature information."
                else:
                    return "Could not retrieve weather information."
            else:
                return f"Error fetching weather data: HTTP {response.status}"

def get_korganizer_events(ics_file_path):
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
        today = datetime.date.today()
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                event_date = component.get('dtstart').dt
                if isinstance(event_date, datetime.datetime):
                    event_date = event_date.date()
                if event_date == today:
                    events.append(component.get('summary'))
        return events
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

def add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
    except FileNotFoundError:
        print(f"Error: Calendar file not found at {ics_file_path}")
        return False  # Indicate failure
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return False

    event = Event()
    event.add('summary', summary)
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    event.add('categories', entry_type)
    cal.add_component(event)

    try:
        with open(ics_file_path, 'wb') as file:
            file.write(cal.to_ical())
        return True  # Indicate success
    except Exception as e:
        print(f"Error writing to calendar file: {e}")
        return False  # Indicate failure

def play_music(music_dirs):
    global vlc_player
    all_music_files = []
    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            all_music_files.extend([os.path.join(music_dir, f) for f in os.listdir(music_dir) if f.endswith(('.mp3', '.mp4'))])
        else:
            print(f"Warning: Directory not found: {music_dir}")
    if all_music_files:
        random_file = random.choice(all_music_files)
        vlc_player = vlc.MediaPlayer(random_file)
        vlc_player.play()
        return f"Now playing: {os.path.basename(random_file)}"
    else:
        return "No music files found in the specified directories."

def play_youtube_audio(query):
    global vlc_player
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            url = info['url']
            title = info['title']
            vlc_player = vlc.MediaPlayer(url)
            vlc_player.play()
            return f"Now playing: {title}"
        except Exception as e:
            print(f"Error playing YouTube audio: {e}")
            return f"Could not play {query} from YouTube."

async def chat_with_ollama(prompt):
    client = Client(host='http://localhost:11434')
    response = client.chat(model='tinyllama', messages=[
        {
            'role': 'user',
            'content': prompt,
        },
    ])
    return response['message']['content']

class TTSEngine:
    def __init__(self, voice="en_US-danny-low"):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def speak(self, text):
        try:
            self.dt.text_2_speech(text, engine="aplay")
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def set_voice(self, voice):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def list_voices(self):
        try:
            voices = Dimits.list_voices()
            print("Available voices:")
            for voice in voices:
                print(voice)
        except Exception as e:
            print(f"Error listing voices: {e}")

def get_intent(text):
    doc = nlp(text)
    intents = {
        "add_entry": ["add", "create", "new", "schedule", "set up"],
        "play_music": ["play", "music", "song", "tune"],
        "youtube": ["youtube", "search youtube", "play on youtube", "watch", "video"],
        "chat": ["chat", "talk", "converse", "speak", "tell me"],
        "exit": ["exit", "quit", "bye", "goodbye", "stop"],
        "weather": ["weather", "temperature", "forecast", "climate"],
        "schedule": ["schedule", "events", "calendar", "agenda", "meetings"],
        "memo": ["memo", "voice memo", "record", "note"],
        "time": ["time", "clock", "what time is it"],
        "date": ["date", "day", "today", "what day is it"],
        "news": ["news", "latest news", "headlines", "updates"],
        "reminder": ["remind", "set reminder", "alarm"],
        "search": ["search", "look up", "find"],
    }
    for intent, keywords in intents.items():
        if any(keyword in text.lower() for keyword in keywords):
            return intent
    return "unknown"

async def handle_weather_intent(tts, location):
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

async def handle_schedule_intent(tts, ics_file_path):
    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

def handle_time_intent(tts):
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}")
    tts.speak(f"The current time is {current_time}")

def handle_date_intent(tts):
    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

# news functionality
async def handle_news_intent(tts):
    print("Fetching the latest news...")
    tts.speak("Fetching the latest news...")

    # List of RSS feeds from various news sources
    rss_feeds = [
        "http://rss.cnn.com/rss/cnn_topstories.rss",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "http://feeds.reuters.com/reuters/topNews",
    ]

    # Choose a random feed
    feed_url = random.choice(rss_feeds)
    
    # Parse the feed
    feed = feedparser.parse(feed_url)
    
    if feed.entries:
        # Get the latest news item
        latest_news = feed.entries[0]
        news_content = f"Latest news: {latest_news.title}. {latest_news.summary}"
    else:
        news_content = "Sorry, I couldn't fetch the latest news at the moment."

    print(news_content)
    tts.speak(news_content)

reminders = []
# reminder functionality
async def check_reminders(tts):
    global reminders
    while True:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for reminder in reminders:
            if reminder["time"] == current_time:
                print(f"Reminder: {reminder['message']}")
                tts.speak(f"Reminder: {reminder['message']}")
                reminders.remove(reminder)
        await asyncio.sleep(60)  # Check every minute

async def handle_reminder_intent(tts):
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")

    reminder_time_str = input("Enter the reminder time (YYYY-MM-DD HH:MM): ")
    reminder_message = input("Enter the reminder message: ")
    
    try:
        reminder_time = datetime.datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
        reminders.append({
            "time": reminder_time.strftime("%Y-%m-%d %H:%M"),
            "message": reminder_message
        })

        reminder_set_message = f"Reminder set for {reminder_time_str}: {reminder_message}"
        print(reminder_set_message)
        tts.speak(reminder_set_message)
    except ValueError:
        error_message = "Invalid date format. Please use YYYY-MM-DD HH:MM."
        print(error_message)
        tts.speak(error_message)

#  search functionality
async def handle_search_intent(tts, query):
    print(f"Searching for: {query}...")
    tts.speak(f"Searching for: {query}...")

    with DDGS() as ddgs:
        results = [r["title"] for r in ddgs.text(query, max_results=3)]

    search_results = ". ".join(results) if results else "No results found."
    print(search_results)
    tts.speak(search_results)

async def ai_assistant(tts):
    time_of_day = get_time_of_day()
    print(f"Good {time_of_day}!")
    tts.speak(f"Good {time_of_day}!")

    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

    location = get_coordinates("New Haven, CT")
    ics_file_path = os.path.expanduser("~/.local/share/evolution/calendar/system/calendar.ics")

    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

    while True:
        print("I'm ready for your command.")
        tts.speak("I'm ready for your command.")
        command = input("Enter your command: ")
        intent = get_intent(command)

        if intent == "add_entry":
            summary = input("Enter the summary of the entry: ")
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(hours=1)
            entry_type = input("Enter the type of entry (todo, reminder, appointment): ")
            if add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
                print(f"Added {entry_type} entry: {summary}")
                tts.speak(f"Added {entry_type} entry: {summary}")
            else:
                print("Failed to add calendar entry.")
                tts.speak("Failed to add calendar entry.")

        elif intent == "play_music":
            music_dirs = ["/home/sam/Music/", "/home/sam/Downloads/"]
            result = play_music(music_dirs)
            print(result)
            tts.speak(result)
        elif intent == "youtube":
            query = input("Enter the YouTube search query: ")
            result = play_youtube_audio(query)
            print(result)
            tts.speak(result)
        elif intent == "chat":
            prompt = input("Enter your message for the AI: ")
            response = await chat_with_ollama(prompt)
            print("AI response:", response)
            tts.speak(response)
        elif intent == "memo":
            await voice_recording.VoiceRecording()
        elif intent == "weather":
            await handle_weather_intent(tts, location)
        elif intent == "schedule":
            handle_schedule_intent(tts, ics_file_path)
        elif intent == "time":
            handle_time_intent(tts)
        elif intent == "date":
            handle_date_intent(tts)
        elif intent == "news":
            await handle_news_intent(tts)
        elif intent == "reminder":
            await handle_reminder_intent(tts)
        elif intent == "search":
            search_query = input("What do you want to search for? ")
            await handle_search_intent(tts, search_query)
        elif intent == "exit":
            print("Goodbye!")
            tts.speak("Goodbye!")
            break
        else:
            print("I'm sorry, I didn't understand that command.")
            tts.speak("I'm sorry, I didn't understand that command.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    tts = TTSEngine()
    asyncio.run(ai_assistant(tts))

```

## Alternate

```
import multiprocessing
import datetime
import aiohttp
import asyncio
import os
import vlc
import yt_dlp
import random
import signal
import sys
from icalendar import Calendar, Event

# --- Third-Party Libraries ---
from ollama import Client
import sounddevice as sd
import numpy as np
import spacy
from dimits import Dimits
import feedparser  # Import feedparser

# --- Constants ---
DEFAULT_VOICE = "en_US-danny-low"  # Centralize default settings
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
NEW_HAVEN_COORDINATES = {"latitude": 41.3083, "longitude": -72.9279, "name": "New Haven, CT"}
DEFAULT_LOCATION_NAME = "New Haven, CT"  # Consider making this configurable
DEFAULT_MUSIC_DIRS = ["/home/sam/Music/", "/home/sam/Downloads/"]
CALENDAR_FILE_PATH = os.path.expanduser("~/.local/share/evolution/calendar/system/calendar.ics")
NEWS_FEED_URL = "http://rss.cnn.com/rss/cnn_topstories.rss"  # Example CNN feed - Make configurable

# --- Global Variables ---
vlc_player = None
nlp = spacy.load("en_core_web_sm")  # Load spaCy model (moved here)

# --- Signal Handling ---
def clean_exit(signum, frame):
    """Handles program exit signals gracefully."""
    print("\nCleaning up and exiting...")
    if vlc_player:
        vlc_player.stop()
    sd.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

# --- Utility Functions ---
def get_time_of_day():
    """Returns the time of day (morning, afternoon, evening)."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 18:
        return "afternoon"
    else:
        return "evening"

def get_date():
    """Returns the current date in a formatted string."""
    return datetime.datetime.now().strftime("%A, %B %d, %Y")

def get_coordinates(location_name):
    """Retrieves coordinates for a given location name."""
    coordinates = {
        DEFAULT_LOCATION_NAME: NEW_HAVEN_COORDINATES
    }
    return coordinates.get(location_name, {"latitude": 0, "longitude": 0, "name": location_name})

def celsius_to_fahrenheit(celsius):
    """Converts Celsius to Fahrenheit."""
    return (celsius * 9/5) + 32

# --- Asynchronous Functions ---
async def get_weather(location):
    """Retrieves weather information for a given location."""
    latitude = location['latitude']
    longitude = location['longitude']
    url = f"{WEATHER_API_URL}?latitude={latitude}&longitude={longitude}&current_weather=true&timezone=America/New_York"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = await response.json()

                weather = data.get('current_weather')
                if not weather:
                    return "Could not retrieve weather information."

                weather_code = weather.get('weathercode', 'unknown')
                temp_celsius = weather.get('temperature', 'N/A')

                if temp_celsius == 'N/A':
                    return "Could not retrieve temperature information."

                temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)

                weather_descriptions = {
                    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                    45: "Fog", 48: "Depositing rime fog",
                    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                    77: "Snow grains",
                    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                    85: "Slight snow showers", 86: "Heavy snow showers",
                    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
                }

                weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")

                return f"The current weather in {location['name']} is {weather_description} with a temperature of {temp_fahrenheit:.1f}°F."

    except aiohttp.ClientError as e:
        return f"Error fetching weather data: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

async def chat_with_ollama(prompt):
    """Chats with the Ollama AI model."""
    try:
        client = Client(host='http://localhost:11434')
        response = await client.chat(model='tinyllama', messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content']
    except Exception as e:
        print(f"Error chatting with Ollama: {e}")
        return "Sorry, I couldn't connect to the AI."

# --- Calendar Functions ---
def get_korganizer_events(ics_file_path):
    """Retrieves today's events from a KOrganizer ICS file."""
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

    today = datetime.date.today()
    events = []
    for component in cal.walk():
        if component.name == "VEVENT":
            event_date = component.get('dtstart').dt
            if isinstance(event_date, datetime.datetime):
                event_date = event_date.date()
            if event_date == today:
                events.append(component.get('summary'))
    return events

def add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
    """Adds a new event to an ICS calendar file."""
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())

        event = Event()
        event.add('summary', summary)
        event.add('dtstart', start_time)
        event.add('dtend', end_time)
        event.add('categories', entry_type)
        cal.add_component(event)

        with open(ics_file_path, 'wb') as file:
            file.write(cal.to_ical())
    except Exception as e:
        print(f"Error adding calendar entry: {e}")

# --- Media Playback Functions ---
def play_music(music_dirs):
    """Plays a random music file from the specified directories."""
    global vlc_player
    all_music_files = []

    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            music_files = [os.path.join(music_dir, f) for f in os.listdir(music_dir) if f.endswith(('.mp3', '.mp4'))]
            all_music_files.extend(music_files)
        else:
            print(f"Warning: Directory not found: {music_dir}")

    if not all_music_files:
        return "No music files found in the specified directories."

    random_file = random.choice(all_music_files)
    try:
        vlc_player = vlc.MediaPlayer(random_file)
        vlc_player.play()
        return f"Now playing: {os.path.basename(random_file)}"
    except Exception as e:
        return f"Error playing music: {e}"

def play_youtube_audio(query):
    """Plays audio from a YouTube video based on a search query."""
    global vlc_player
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' not in info or not info['entries']:
                return "No YouTube videos found for that query."

            url = info['entries'][0]['url']
            title = info['entries'][0]['title']

            vlc_player = vlc.MediaPlayer(url)
            vlc_player.play()
            return f"Now playing: {title}"

    except Exception as e:
        return f"Error playing YouTube audio: {e}"

# --- TTS Engine ---
class TTSEngine:
    """Text-to-speech engine using Dimits."""

    def __init__(self, voice=DEFAULT_VOICE):
        """Initializes the TTSEngine with a specified voice."""
        self.voice = voice
        self.dt = Dimits(self.voice)

    def speak(self, text):
        """Speaks the given text using the TTS engine."""
        try:
            self.dt.text_2_speech(text, engine="aplay")
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def set_voice(self, voice):
        """Sets the voice for the TTS engine."""
        self.voice = voice
        self.dt = Dimits(self.voice)

    def list_voices(self):
        """Lists available voices (if supported by Dimits)."""
        try:
            voices = Dimits.list_voices()
            print("Available voices:")
            for voice in voices:
                print(voice)
        except Exception as e:
            print(f"Error listing voices: {e}")

# --- Intent Recognition ---
def get_intent(text):
    """Identifies the user's intent from the input text."""
    text = text.lower()  # Convert to lowercase once for efficiency
    intents = {
        "add_entry": ["add", "create", "schedule", "set up", "plan"],  # Removed 'new'
        "play_music": ["play", "music", "song", "tune", "audio"],
        "youtube": ["youtube", "search youtube", "play on youtube", "watch", "video"],
        "chat": ["chat", "talk", "converse", "speak", "tell me"],
        "exit": ["exit", "quit", "bye", "goodbye", "stop", "end"],
        "weather": ["weather", "temperature", "forecast", "climate", "conditions"],
        "schedule": ["schedule", "events", "calendar", "agenda", "meetings", "appointments"],
        "memo": ["memo", "voice memo", "record", "note", "dictate"],
        "time": ["time", "clock", "what time is it"],
        "date": ["date", "day", "today", "what day is it"],
        "news": ["news", "latest news", "headlines", "updates", "current events"],
        "reminder": ["remind", "set reminder", "alarm", "notify"],
        "search": ["search", "look up", "find", "google"],  # added google
    }
    for intent, keywords in intents.items():
        if any(keyword in text for keyword in keywords):
            return intent
    return "unknown"

# --- Intent Handlers ---
async def handle_weather_intent(tts, location):
    """Handles the weather intent."""
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

def handle_schedule_intent(tts, ics_file_path):
    """Handles the schedule intent."""
    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

def handle_time_intent(tts):
    """Handles the time intent."""
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}")
    tts.speak(f"The current time is {current_time}")

def handle_date_intent(tts):
    """Handles the date intent."""
    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

def handle_news_intent(tts):
    """Handles the news intent by fetching and speaking the latest news."""
    print("Fetching the latest news...")
    tts.speak("Fetching the latest news...")

    try:
        news_feed = feedparser.parse(NEWS_FEED_URL)  # Use a constant for the URL

        if hasattr(news_feed, 'entries') and news_feed.entries: #Check is entries is an attribute and if it contains a value.
            for entry in news_feed.entries[:3]:  # Speak the first 3 headlines
                title = entry.get('title', 'No title')  # Safely get the title
                summary = entry.get('summary', 'No summary available')  # Safely get the summary
                news_content = f"Latest news: {title}. {summary}"  # Create a combined string
                print(news_content)
                tts.speak(news_content)
        else:
            print("Could not retrieve news feed or no entries found.")
            tts.speak("Could not retrieve news feed or no entries found.")

    except Exception as e:
        error_message = f"Could not retrieve news: {e}"
        print(error_message)
        tts.speak(error_message)

async def handle_reminder_intent(tts):
    """Handles the reminder intent (placeholder)."""
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")
    # Implement your reminder setting logic here (e.g., using a scheduling library)
    reminder_set_message = "Reminder set for the specified time."  # Replace with actual confirmation
    print(reminder_set_message)
    tts.speak(reminder_set_message)

async def handle_search_intent(tts, query):
    """Handles the search intent (placeholder)."""
    print(f"Searching for: {query}...")
    tts.speak(f"Searching for: {query}...")
    # Implement your search logic here (e.g., using a search engine API)
    search_results = "This is a placeholder for search results."  # Replace with actual results
    print(search_results)
    tts.speak(search_results)

# --- Main Assistant Function ---
async def ai_assistant(tts):
    """Main function for the AI assistant."""

    # Initial Greeting
    time_of_day = get_time_of_day()
    date = get_date()
    print(f"Good {time_of_day}! Today is {date}.")
    tts.speak(f"Good {time_of_day}! Today is {date}.")

    # Initial Information
    location = get_coordinates(DEFAULT_LOCATION_NAME)
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

    events = get_korganizer_events(CALENDAR_FILE_PATH)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

    # Command Loop
    while True:
        print("I'm ready for your command.")
        tts.speak("I'm ready for your command.")
        command = input("Enter your command: ")
        intent = get_intent(command)

        if intent == "add_entry":
            summary = input("Enter the summary of the entry: ")
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(hours=1)
            entry_type = input("Enter the type of entry (todo, reminder, appointment): ")
            add_ical_entry(CALENDAR_FILE_PATH, summary, start_time, end_time, entry_type)
            print(f"Added {entry_type} entry: {summary}")
            tts.speak(f"Added {entry_type} entry: {summary}")

        elif intent == "play_music":
            result = play_music(DEFAULT_MUSIC_DIRS)
            print(result)
            tts.speak(result)

        elif intent == "youtube":
            query = input("Enter the YouTube search query: ")
            result = play_youtube_audio(query)
            print(result)
            tts.speak(result)

        elif intent == "chat":
            prompt = input("Enter your message for the AI: ")
            response = await chat_with_ollama(prompt)
            print("AI response:", response)
            tts.speak(response)

        elif intent == "memo":
            print("Voice memo functionality is not yet fully implemented.")  # Provide feedback
            tts.speak("Voice memo functionality is not yet fully implemented.")
            # await voice_recording.VoiceRecording()  # Ensure voice_recording is defined

        elif intent == "weather":
            await handle_weather_intent(tts, location)

        elif intent == "schedule":
            handle_schedule_intent(tts, CALENDAR_FILE_PATH)

        elif intent == "time":
            handle_time_intent(tts)

        elif intent == "date":
            handle_date_intent(tts)

        elif intent == "news":
            handle_news_intent(tts)  #Call news_intent

        elif intent == "reminder":
            await handle_reminder_intent(tts)

        elif intent == "search":
            search_query = input("What do you want to search for? ")
            await handle_search_intent(tts, search_query)

        elif intent == "exit":
            print("Goodbye!")
            tts.speak("Goodbye!")
            break

        else:
            print("I'm sorry, I didn't understand that command.")
            tts.speak("I'm sorry, I didn't understand that command.")

# --- Main Execution ---
if __name__ == "__main__":
    multiprocessing.freeze_support()
    tts = TTSEngine()
    asyncio.run(ai_assistant(tts))
```



Another revised version to fix the syntax issues:

```
import multiprocessing
import datetime
import aiohttp
import asyncio
import os
import vlc
import yt_dlp
import random
from ollama import Client
import sounddevice as sd
import spacy
import signal
import sys
from icalendar import Calendar, Event
from dimits import Dimits

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Global variables
vlc_player = None

def clean_exit(signum, frame):
    print("\nCleaning up and exiting...")
    if vlc_player:
        vlc_player.stop()
    sd.stop()
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

def get_time_of_day():
    current_time = datetime.datetime.now()
    if current_time.hour < 12:
        return "morning"
    elif 12 <= current_time.hour < 18:
        return "afternoon"
    else:
        return "evening"

def get_date():
    return datetime.datetime.now().strftime("%A, %B %d, %Y")

def get_coordinates(location_name):
    coordinates = {
        "New Haven, CT": {"latitude": 41.3083, "longitude": -72.9279, "name": location_name},
    }
    return coordinates.get(location_name, {"latitude": 0, "longitude": 0, "name": location_name})

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

async def get_weather(location):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={location['latitude']}&longitude={location['longitude']}&current_weather=true&timezone=America/New_York"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if 'current_weather' in data:
                    weather = data['current_weather']
                    weather_code = weather.get('weathercode', 'unknown')
                    temp_celsius = weather.get('temperature', 'N/A')

                    if temp_celsius != 'N/A':
                        temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)

                        # Weather code descriptions
                        weather_descriptions = {
                            0: "Clear sky",
                            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                            45: "Fog", 48: "Depositing rime fog",
                            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                            77: "Snow grains",
                            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                            85: "Slight snow showers", 86: "Heavy snow showers",
                            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
                        }

                        weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")

                        return f"The current weather in {location['name']} is {weather_description} with a temperature of {temp_fahrenheit:.1f}°F."
                    else:
                        return "Could not retrieve temperature information."
                else:
                    return "Could not retrieve weather information."
            else:
                return f"Error fetching weather data: HTTP {response.status}"

def get_korganizer_events(ics_file_path):
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
        today = datetime.date.today()
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                event_date = component.get('dtstart').dt
                if isinstance(event_date, datetime.datetime):
                    event_date = event_date.date()
                if event_date == today:
                    events.append(component.get('summary'))
        return events
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

def add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
    with open(ics_file_path, 'rb') as file:
        cal = Calendar.from_ical(file.read())
    event = Event()
    event.add('summary', summary)
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    event.add('categories', entry_type)
    cal.add_component(event)
    with open(ics_file_path, 'wb') as file:
        file.write(cal.to_ical())

def play_music(music_dirs):
    global vlc_player
    all_music_files = []
    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            all_music_files.extend([os.path.join(music_dir, f) for f in os.listdir(music_dir) if f.endswith(('.mp3', '.mp4'))])
        else:
            print(f"Warning: Directory not found: {music_dir}")
    if all_music_files:
        random_file = random.choice(all_music_files)
        vlc_player = vlc.MediaPlayer(random_file)
        vlc_player.play()
        return f"Now playing: {os.path.basename(random_file)}"
    else:
        return "No music files found in the specified directories."

def play_youtube_audio(query):
    global vlc_player
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
        url = info['url']
        title = info['title']
        vlc_player = vlc.MediaPlayer(url)
        vlc_player.play()
        return f"Now playing: {title}"

async def chat_with_ollama(prompt):
    client = Client(host='http://localhost:11434')
    response = client.chat(model='tinyllama', messages=[
        {
            'role': 'user',
            'content': prompt,
        },
    ])
    return response['message']['content']

class TTSEngine:
    def __init__(self, voice="en_US-danny-low"):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def speak(self, text):
        try:
            self.dt.text_2_speech(text, engine="aplay")
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def set_voice(self, voice):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def list_voices(self):
        try:
            voices = Dimits.list_voices()
            print("Available voices:")
            for voice in voices:
                print(voice)
        except Exception as e:
            print(f"Error listing voices: {e}")

def get_intent(text):
    doc = nlp(text)
    intents = {
        "add_entry": ["add", "create", "new", "schedule", "set up"],
        "play_music": ["play", "music", "song", "tune"],
        "youtube": ["youtube", "search youtube", "play on youtube", "watch", "video"],
        "chat": ["chat", "talk", "converse", "speak", "tell me"],
        "exit": ["exit", "quit", "bye", "goodbye", "stop"],
        "weather": ["weather", "temperature", "forecast", "climate"],
        "schedule": ["schedule", "events", "calendar", "agenda", "meetings"],
        "memo": ["memo", "voice memo", "record", "note"],
        "time": ["time", "clock", "what time is it"],
        "date": ["date", "day", "today", "what day is it"],
        "news": ["news", "latest news", "headlines", "updates"],
        "reminder": ["remind", "set reminder", "alarm"],
        "search": ["search", "look up", "find"],
    }
    for intent, keywords in intents.items():
        if any(keyword in text.lower() for keyword in keywords):
            return intent
    return "unknown"

async def handle_weather_intent(tts, location):
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

def handle_schedule_intent(tts, ics_file_path):
    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

def handle_time_intent(tts):
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}")
    tts.speak(f"The current time is {current_time}")

def handle_date_intent(tts):
    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

# Placeholder for news functionality
async def handle_news_intent(tts):
    print("Fetching the latest news...")
    tts.speak("Fetching the latest news...")
    # Implement your news fetching logic here (e.g., using an API)
    news_content = "This is a placeholder for the latest news."  # Replace with actual news
    print(news_content)
    tts.speak(news_content)

# Placeholder for reminder functionality
async def handle_reminder_intent(tts):
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")
    # Implement your reminder setting logic here (e.g., using a scheduling library)
    reminder_set_message = "Reminder set for the specified time."  # Replace with actual confirmation
    print(reminder_set_message)
    tts.speak(reminder_set_message)

# Placeholder for search functionality
async def handle_search_intent(tts, query):
    print(f"Searching for: {query}...")
    tts.speak(f"Searching for: {query}...")
    # Implement your search logic here (e.g., using a search engine API)
    search_results = "This is a placeholder for search results."  # Replace with actual results
    print(search_results)
    tts.speak(search_results)

async def ai_assistant(tts):
    time_of_day = get_time_of_day()
    print(f"Good {time_of_day}!")
    tts.speak(f"Good {time_of_day}!")

    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

    location = get_coordinates("New Haven, CT")
    ics_file_path = os.path.expanduser("~/.local/share/evolution/calendar/system/calendar.ics")

    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

    while True:
        print("I'm ready for your command.")
        tts.speak("I'm ready for your command.")
        command = input("Enter your command: ")
        intent = get_intent(command)

        if intent == "add_entry":
            summary = input("Enter the summary of the entry: ")
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(hours=1)
            entry_type = input("Enter the type of entry (todo, reminder, appointment): ")
            add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type)
            print(f"Added {entry_type} entry: {summary}")
            tts.speak(f"Added {entry_type} entry: {summary}")
        elif intent == "play_music":
            music_dirs = ["/home/sam/Music/", "/home/sam/Downloads/"]
            result = play_music(music_dirs)
            print(result)
            tts.speak(result)
        elif intent == "youtube":
            query = input("Enter the YouTube search query: ")
            result = play_youtube_audio(query)
            print(result)
            tts.speak(result)
        elif intent == "chat":
            prompt = input("Enter your message for the AI: ")
            response = await chat_with_ollama(prompt)
            print("AI response:", response)
            tts.speak(response)
        elif intent == "memo":
            await voice_recording.VoiceRecording()
        elif intent == "weather":
            await handle_weather_intent(tts, location)
        elif intent == "schedule":
            handle_schedule_intent(tts, ics_file_path)
        elif intent == "time":
            handle_time_intent(tts)
        elif intent == "date":
            handle_date_intent(tts)
        elif intent == "news":
            await handle_news_intent(tts)
        elif intent == "reminder":
            await handle_reminder_intent(tts)
        elif intent == "search":
            search_query = input("What do you want to search for? ")
            await handle_search_intent(tts, search_query)
        elif intent == "exit":
            print("Goodbye!")
            tts.speak("Goodbye!")
            break
        else:
            print("I'm sorry, I didn't understand that command.")
            tts.speak("I'm sorry, I didn't understand that command.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    tts = TTSEngine()
    asyncio.run(ai_assistant(tts))
```    


## This is updated version processed from Perplexity:

```
import multiprocessing
import datetime
import aiohttp
import asyncio
import os
import vlc
import yt_dlp
import random
from ollama import Client
import sounddevice as sd
import spacy
import signal
import sys
from icalendar import Calendar, Event
from dimits import Dimits

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Global variables
vlc_player = None

def clean_exit(signum, frame):
    print("\nCleaning up and exiting...")
    if vlc_player:
        vlc_player.stop()
    sd.stop()
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

def get_time_of_day():
    current_time = datetime.datetime.now()
    if current_time.hour < 12:
        return "morning"
    elif 12 <= current_time.hour < 18:
        return "afternoon"
    else:
        return "evening"

def get_date():
    return datetime.datetime.now().strftime("%A, %B %d, %Y")

def get_coordinates(location_name):
    coordinates = {
        "New Haven, CT": {"latitude": 41.3083, "longitude": -72.9279, "name": location_name},
    }
    return coordinates.get(location_name, {"latitude": 0, "longitude": 0, "name": location_name})

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

async def get_weather(location):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={location['latitude']}&longitude={location['longitude']}&current_weather=true&timezone=America/New_York"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if 'current_weather' in data:
                    weather = data['current_weather']
                    weather_code = weather.get('weathercode', 'unknown')
                    temp_celsius = weather.get('temperature', 'N/A')

                    if temp_celsius != 'N/A':
                        temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)

                        # Weather code descriptions
                        weather_descriptions = {
                            0: "Clear sky",
                            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                            45: "Fog", 48: "Depositing rime fog",
                            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                            77: "Snow grains",
                            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                            85: "Slight snow showers", 86: "Heavy snow showers",
                            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
                        }

                        weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")

                        return f"The current weather in {location['name']} is {weather_description} with a temperature of {temp_fahrenheit:.1f}°F."
                    else:
                        return "Could not retrieve temperature information."
                else:
                    return "Could not retrieve weather information."
            else:
                return f"Error fetching weather data: HTTP {response.status}"

def get_korganizer_events(ics_file_path):
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
        today = datetime.date.today()
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                event_date = component.get('dtstart').dt
                if isinstance(event_date, datetime.datetime):
                    event_date = event_date.date()
                if event_date == today:
                    events.append(component.get('summary'))
        return events
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

def add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
    with open(ics_file_path, 'rb') as file:
        cal = Calendar.from_ical(file.read())
    event = Event()
    event.add('summary', summary)
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    event.add('categories', entry_type)
    cal.add_component(event)
    with open(ics_file_path, 'wb') as file:
        file.write(cal.to_ical())

def play_music(music_dirs):
    global vlc_player
    all_music_files = []
    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            all_music_files.extend([os.path.join(music_dir, f) for f in os.listdir(music_dir) if f.endswith(('.mp3', '.mp4'))])
        else:
            print(f"Warning: Directory not found: {music_dir}")
    if all_music_files:
        random_file = random.choice(all_music_files)
        vlc_player = vlc.MediaPlayer(random_file)
        vlc_player.play()
        return f"Now playing: {os.path.basename(random_file)}"
    else:
        return "No music files found in the specified directories."

def play_youtube_audio(query):
    global vlc_player
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
        url = info['url']
        title = info['title']
        vlc_player = vlc.MediaPlayer(url)
        vlc_player.play()
        return f"Now playing: {title}"

async def chat_with_ollama(prompt):
    client = Client(host='http://localhost:11434')
    response = client.chat(model='tinyllama', messages=[
        {
            'role': 'user',
            'content': prompt,
        },
    ])
    return response['message']['content']

class TTSEngine:
    def __init__(self, voice="en_US-danny-low"):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def speak(self, text):
        try:
            self.dt.text_2_speech(text, engine="aplay")
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def set_voice(self, voice):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def list_voices(self):
        try:
            voices = Dimits.list_voices()
            print("Available voices:")
            for voice in voices:
                print(voice)
        except Exception as e:
            print(f"Error listing voices: {e}")

def get_intent(text):
    doc = nlp(text)
    intents = {
        "add_entry": ["add", "create", "new", "schedule", "set up"],
        "play_music": ["play", "music", "song", "tune"],
        "youtube": ["youtube", "search youtube", "play on youtube", "watch", "video"],
        "chat": ["chat", "talk", "converse", "speak", "tell me"],
        "exit": ["exit", "quit", "bye", "goodbye", "stop"],
        "weather": ["weather", "temperature", "forecast", "climate"],
        "schedule": ["schedule", "events", "calendar", "agenda", "meetings"],
        "memo": ["memo", "voice memo", "record", "note"],
        "time": ["time", "clock", "what time is it"],
        "date": ["date", "day", "today", "what day is it"],
        "news": ["news", "latest news", "headlines", "updates"],
        "reminder": ["remind", "set reminder", "alarm"],
        "search": ["search", "look up", "find"],
    }
    for intent, keywords in intents.items():
        if any(keyword in text.lower() for keyword in keywords):
            return intent
    return "unknown"

async def handle_weather_intent(tts, location):
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

def handle_schedule_intent(tts, ics_file_path):
    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

def handle_time_intent(tts):
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}")
    tts.speak(f"The current time is {current_time}")

def handle_date_intent(tts):
    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

# Placeholder for news functionality
async def handle_news_intent(tts):
    print("Fetching the latest news...")
    tts.speak("Fetching the latest news...")
    # Implement your news fetching logic here (e.g., using an API)
    news_content = "This is a placeholder for the latest news."  # Replace with actual news
    print(news_content)
    tts.speak(news_content)

# Placeholder for reminder functionality
async def handle_reminder_intent(tts):
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")
    # Implement your reminder setting logic here (e.g., using a scheduling library)
    reminder_set_message = "Reminder set for the specified time."  # Replace with actual confirmation
    print(reminder_set_message)
    tts.speak(reminder_set_message)

# Placeholder for search functionality
async def handle_search_intent(tts, query):
    print(f"Searching for: {query}...")
    tts.speak(f"Searching for: {query}...")
    # Implement your search logic here (e.g., using a search engine API)
    search_results = "This is a placeholder for search results."  # Replace with actual results
    print(search_results)
    tts.speak(search_results)

async def ai_assistant(tts):
    time_of_day = get_time_of_day()
    print(f"Good {time_of_day}!")
    tts.speak(f"Good {time_of_day}!")

    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

    location = get_coordinates("New Haven, CT")
    ics_file_path = os.path.expanduser("~/.local/share/evolution/calendar/system/calendar.ics")

    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

    while True:
        print("I'm ready for your command.")
        tts.speak("I'm ready for your command.")
        command = input("Enter your command: ")
        intent = get_intent(command)

        if intent == "add_entry":
            summary = input("Enter the summary of the entry: ")
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(hours=1)
            entry_type = input("Enter the type of entry (todo, reminder, appointment): ")
            add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type)
            print(f"Added {entry_type} entry: {summary}")
            tts.speak(f"Added {entry_type} entry: {summary}")
        elif intent == "play_music":
            music_dirs = ["/home/sam/Music/", "/home/sam/Downloads/"]
            result = play_music(music_dirs)
            print(result)
            tts.speak(result)
        elif intent == "youtube":
            query = input("Enter the YouTube search query: ")
            result = play_youtube_audio(query)
            print(result)
            tts.speak(result)
        elif intent == "chat":
            prompt = input("Enter your message for the AI: ")
            response = await chat_with_ollama(prompt)
            print("AI response:", response)
            tts.speak(response)
        elif intent == "memo":
            await voice_recording.VoiceRecording()
        elif intent == "weather":
            await handle_weather_intent(tts, location)
        elif intent == "schedule":
            handle_schedule_intent(tts, ics_file_path)
        elif intent == "time":
            handle_time_intent(tts)
        elif intent == "date":
            handle_date_intent(tts)
        elif intent == "news":
            await handle_news_intent(tts)
        elif intent == "reminder":
            await handle_reminder_intent(tts)
        elif intent == "search":
            search_query = input("What do you want to search for? ")
            await handle_search_intent(tts, search_query)
        elif intent == "exit":
            print("Goodbye!")
            tts.speak("Goodbye!")
            break
        else:
            print("I'm sorry, I didn't understand that command.")
            tts.speak("I'm sorry, I didn't understand that command.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    tts = TTSEngine()
    asyncio.run(ai_assistant(tts))
```

## Revised with News Segment:

```
import multiprocessing
import datetime
import aiohttp
import asyncio
import os
import vlc
import yt_dlp
import random
import signal
import sys
from icalendar import Calendar, Event

# --- Third-Party Libraries ---
from ollama import Client
import sounddevice as sd
import numpy as np
import spacy
from dimits import Dimits

# --- Constants ---
DEFAULT_VOICE = "en_US-danny-low"  # Centralize default settings
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
NEW_HAVEN_COORDINATES = {"latitude": 41.3083, "longitude": -72.9279, "name": "New Haven, CT"}
DEFAULT_LOCATION_NAME = "New Haven, CT" # Consider making this configurable
DEFAULT_MUSIC_DIRS = ["/home/sam/Music/", "/home/sam/Downloads/"]
CALENDAR_FILE_PATH = os.path.expanduser("~/.local/share/evolution/calendar/system/calendar.ics")

# --- Global Variables ---
vlc_player = None
nlp = spacy.load("en_core_web_sm")  # Load spaCy model (moved here)

# --- Signal Handling ---
def clean_exit(signum, frame):
    """Handles program exit signals gracefully."""
    print("\nCleaning up and exiting...")
    if vlc_player:
        vlc_player.stop()
    sd.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

# --- Utility Functions ---
def get_time_of_day():
    """Returns the time of day (morning, afternoon, evening)."""
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 18:
        return "afternoon"
    else:
        return "evening"

def get_date():
    """Returns the current date in a formatted string."""
    return datetime.datetime.now().strftime("%A, %B %d, %Y")

def get_coordinates(location_name):
    """Retrieves coordinates for a given location name."""
    coordinates = {
        DEFAULT_LOCATION_NAME: NEW_HAVEN_COORDINATES
    }
    return coordinates.get(location_name, {"latitude": 0, "longitude": 0, "name": location_name})

def celsius_to_fahrenheit(celsius):
    """Converts Celsius to Fahrenheit."""
    return (celsius * 9/5) + 32

# --- Asynchronous Functions ---
async def get_weather(location):
    """Retrieves weather information for a given location."""
    latitude = location['latitude']
    longitude = location['longitude']
    url = f"{WEATHER_API_URL}?latitude={latitude}&longitude={longitude}&current_weather=true&timezone=America/New_York"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = await response.json()

                weather = data.get('current_weather')
                if not weather:
                    return "Could not retrieve weather information."

                weather_code = weather.get('weathercode', 'unknown')
                temp_celsius = weather.get('temperature', 'N/A')

                if temp_celsius == 'N/A':
                    return "Could not retrieve temperature information."

                temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)

                weather_descriptions = {
                    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                    45: "Fog", 48: "Depositing rime fog",
                    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                    77: "Snow grains",
                    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                    85: "Slight snow showers", 86: "Heavy snow showers",
                    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
                }

                weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")

                return f"The current weather in {location['name']} is {weather_description} with a temperature of {temp_fahrenheit:.1f}°F."

    except aiohttp.ClientError as e:
        return f"Error fetching weather data: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

async def chat_with_ollama(prompt):
    """Chats with the Ollama AI model."""
    try:
        client = Client(host='http://localhost:11434')
        response = await client.chat(model='tinyllama', messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content']
    except Exception as e:
        print(f"Error chatting with Ollama: {e}")
        return "Sorry, I couldn't connect to the AI."

# --- Calendar Functions ---
def get_korganizer_events(ics_file_path):
    """Retrieves today's events from a KOrganizer ICS file."""
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

    today = datetime.date.today()
    events = []
    for component in cal.walk():
        if component.name == "VEVENT":
            event_date = component.get('dtstart').dt
            if isinstance(event_date, datetime.datetime):
                event_date = event_date.date()
            if event_date == today:
                events.append(component.get('summary'))
    return events

def add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
    """Adds a new event to an ICS calendar file."""
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())

        event = Event()
        event.add('summary', summary)
        event.add('dtstart', start_time)
        event.add('dtend', end_time)
        event.add('categories', entry_type)
        cal.add_component(event)

        with open(ics_file_path, 'wb') as file:
            file.write(cal.to_ical())
    except Exception as e:
        print(f"Error adding calendar entry: {e}")

# --- Media Playback Functions ---
def play_music(music_dirs):
    """Plays a random music file from the specified directories."""
    global vlc_player
    all_music_files = []

    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            music_files = [os.path.join(music_dir, f) for f in os.listdir(music_dir) if f.endswith(('.mp3', '.mp4'))]
            all_music_files.extend(music_files)
        else:
            print(f"Warning: Directory not found: {music_dir}")

    if not all_music_files:
        return "No music files found in the specified directories."

    random_file = random.choice(all_music_files)
    try:
        vlc_player = vlc.MediaPlayer(random_file)
        vlc_player.play()
        return f"Now playing: {os.path.basename(random_file)}"
    except Exception as e:
        return f"Error playing music: {e}"

def play_youtube_audio(query):
    """Plays audio from a YouTube video based on a search query."""
    global vlc_player
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' not in info or not info['entries']:
                return "No YouTube videos found for that query."

            url = info['entries'][0]['url']
            title = info['entries'][0]['title']

            vlc_player = vlc.MediaPlayer(url)
            vlc_player.play()
            return f"Now playing: {title}"

    except Exception as e:
        return f"Error playing YouTube audio: {e}"

# --- TTS Engine ---
class TTSEngine:
    """Text-to-speech engine using Dimits."""

    def __init__(self, voice=DEFAULT_VOICE):
        """Initializes the TTSEngine with a specified voice."""
        self.voice = voice
        self.dt = Dimits(self.voice)

    def speak(self, text):
        """Speaks the given text using the TTS engine."""
        try:
            self.dt.text_2_speech(text, engine="aplay")
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def set_voice(self, voice):
        """Sets the voice for the TTS engine."""
        self.voice = voice
        self.dt = Dimits(self.voice)

    def list_voices(self):
        """Lists available voices (if supported by Dimits)."""
        try:
            voices = Dimits.list_voices()
            print("Available voices:")
            for voice in voices:
                print(voice)
        except Exception as e:
            print(f"Error listing voices: {e}")

# --- Intent Recognition ---
def get_intent(text):
    """Identifies the user's intent from the input text."""
    text = text.lower()  # Convert to lowercase once for efficiency
    intents = {
        "add_entry": ["add", "create", "new", "schedule", "set up", "plan"],
        "play_music": ["play", "music", "song", "tune", "audio"],
        "youtube": ["youtube", "search youtube", "play on youtube", "watch", "video"],
        "chat": ["chat", "talk", "converse", "speak", "tell me"],
        "exit": ["exit", "quit", "bye", "goodbye", "stop", "end"],
        "weather": ["weather", "temperature", "forecast", "climate", "conditions"],
        "schedule": ["schedule", "events", "calendar", "agenda", "meetings", "appointments"],
        "memo": ["memo", "voice memo", "record", "note", "dictate"],
        "time": ["time", "clock", "what time is it"],
        "date": ["date", "day", "today", "what day is it"],
        "news": ["news", "latest news", "headlines", "updates", "current events"],
        "reminder": ["remind", "set reminder", "alarm", "notify"],
        "search": ["search", "look up", "find", "google"],  #added google
    }
    for intent, keywords in intents.items():
        if any(keyword in text for keyword in keywords):
            return intent
    return "unknown"

# --- Intent Handlers ---
async def handle_weather_intent(tts, location):
    """Handles the weather intent."""
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

def handle_schedule_intent(tts, ics_file_path):
    """Handles the schedule intent."""
    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

def handle_time_intent(tts):
    """Handles the time intent."""
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}")
    tts.speak(f"The current time is {current_time}")

def handle_date_intent(tts):
    """Handles the date intent."""
    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

async def handle_news_intent(tts):
    """Handles the news intent (placeholder)."""
    print("Fetching the latest news...")
    tts.speak("Fetching the latest news...")
    # Implement your news fetching logic here (e.g., using an API)
    news_content = "This is a placeholder for the latest news."  # Replace with actual news
    print(news_content)
    tts.speak(news_content)

async def handle_reminder_intent(tts):
    """Handles the reminder intent (placeholder)."""
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")
    # Implement your reminder setting logic here (e.g., using a scheduling library)
    reminder_set_message = "Reminder set for the specified time."  # Replace with actual confirmation
    print(reminder_set_message)
    tts.speak(reminder_set_message)

async def handle_search_intent(tts, query):
    """Handles the search intent (placeholder)."""
    print(f"Searching for: {query}...")
    tts.speak(f"Searching for: {query}...")
    # Implement your search logic here (e.g., using a search engine API)
    search_results = "This is a placeholder for search results."  # Replace with actual results
    print(search_results)
    tts.speak(search_results)

# --- Main Assistant Function ---
async def ai_assistant(tts):
    """Main function for the AI assistant."""

    # Initial Greeting
    time_of_day = get_time_of_day()
    date = get_date()
    print(f"Good {time_of_day}! Today is {date}.")
    tts.speak(f"Good {time_of_day}! Today is {date}.")

    # Initial Information
    location = get_coordinates(DEFAULT_LOCATION_NAME)
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

    events = get_korganizer_events(CALENDAR_FILE_PATH)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

    # Command Loop
    while True:
        print("I'm ready for your command.")
        tts.speak("I'm ready for your command.")
        command = input("Enter your command: ")
        intent = get_intent(command)

        if intent == "add_entry":
            summary = input("Enter the summary of the entry: ")
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(hours=1)
            entry_type = input("Enter the type of entry (todo, reminder, appointment): ")
            add_ical_entry(CALENDAR_FILE_PATH, summary, start_time, end_time, entry_type)
            print(f"Added {entry_type} entry: {summary}")
            tts.speak(f"Added {entry_type} entry: {summary}")

        elif intent == "play_music":
            result = play_music(DEFAULT_MUSIC_DIRS)
            print(result)
            tts.speak(result)

        elif intent == "youtube":
            query = input("Enter the YouTube search query: ")
            result = play_youtube_audio(query)
            print(result)
            tts.speak(result)

        elif intent == "chat":
            prompt = input("Enter your message for the AI: ")
            response = await chat_with_ollama(prompt)
            print("AI response:", response)
            tts.speak(response)

        elif intent == "memo":
            print("Voice memo functionality is not yet fully implemented.")  #Provide feedback
            tts.speak("Voice memo functionality is not yet fully implemented.")
            #await voice_recording.VoiceRecording() #Ensure the VoiceRecording class is properly imported and defined

        elif intent == "weather":
            await handle_weather_intent(tts, location)

        elif intent == "schedule":
            handle_schedule_intent(tts, CALENDAR_FILE_PATH)

        elif intent == "time":
            handle_time_intent(tts)

        elif intent == "date":
            handle_date_intent(tts)

        elif intent == "news":
            await handle_news_intent(tts)

        elif intent == "reminder":
            await handle_reminder_intent(tts)

        elif intent == "search":
            search_query = input("What do you want to search for? ")
            await handle_search_intent(tts, search_query)

        elif intent == "exit":
            print("Goodbye!")
            tts.speak("Goodbye!")
            break

        else:
            print("I'm sorry, I didn't understand that command.")
            tts.speak("I'm sorry, I didn't understand that command.")

# --- Main Execution ---
if __name__ == "__main__":
    multiprocessing.freeze_support()
    tts = TTSEngine()
    asyncio.run(ai_assistant(tts))
```
# Pain 1.2 Version

```
import multiprocessing
import feedparser
import random
import datetime
import aiohttp
import asyncio
import os
import vlc
import yt_dlp
from ollama import Client
import sounddevice as sd
import spacy
import signal
import sys
from icalendar import Calendar, Event
from duckduckgo_search import DDGS
from dimits import Dimits
import subprocess  # Import the subprocess module

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Global variables
vlc_player = None

def clean_exit(signum, frame):
    print("\nCleaning up and exiting...")
    if vlc_player:
        vlc_player.stop()
    sd.stop()
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

def get_time_of_day():
    current_time = datetime.datetime.now()
    if current_time.hour < 12:
        return "morning"
    elif 12 <= current_time.hour < 18:
        return "afternoon"
    else:
        return "evening"

def get_date():
    return datetime.datetime.now().strftime("%A, %B %d, %Y")

def get_coordinates(location_name):
    coordinates = {
        "New Haven, CT": {"latitude": 41.3083, "longitude": -72.9279, "name": location_name},
    }
    return coordinates.get(location_name, {"latitude": 0, "longitude": 0, "name": location_name})

def celsius_to_fahrenheit(celsius):
    return (celsius * 9/5) + 32

async def get_weather(location):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={location['latitude']}&longitude={location['longitude']}&current_weather=true&timezone=America/New_York"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if 'current_weather' in data:
                    weather = data['current_weather']
                    weather_code = weather.get('weathercode', 'unknown')
                    temp_celsius = weather.get('temperature', 'N/A')

                    if temp_celsius != 'N/A':
                        temp_fahrenheit = celsius_to_fahrenheit(temp_celsius)

                        # Weather code descriptions
                        weather_descriptions = {
                            0: "Clear sky",
                            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                            45: "Fog", 48: "Depositing rime fog",
                            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
                            77: "Snow grains",
                            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                            85: "Slight snow showers", 86: "Heavy snow showers",
                            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
                        }

                        weather_description = weather_descriptions.get(weather_code, "Unknown weather condition")

                        return f"The current weather in {location['name']} is {weather_description} with a temperature of {temp_fahrenheit:.1f}°F."
                    else:
                        return "Could not retrieve temperature information."
                else:
                    return "Could not retrieve weather information."
            else:
                return f"Error fetching weather data: HTTP {response.status}"

def get_korganizer_events(ics_file_path):
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
        today = datetime.date.today()
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                event_date = component.get('dtstart').dt
                if isinstance(event_date, datetime.datetime):
                    event_date = event_date.date()
                if event_date == today:
                    events.append(component.get('summary'))
        return events
    except FileNotFoundError:
        print(f"Calendar file not found: {ics_file_path}")
        return []
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return []

def add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
    try:
        with open(ics_file_path, 'rb') as file:
            cal = Calendar.from_ical(file.read())
    except FileNotFoundError:
        print(f"Error: Calendar file not found at {ics_file_path}")
        return False  # Indicate failure
    except Exception as e:
        print(f"Error reading calendar file: {e}")
        return False

    event = Event()
    event.add('summary', summary)
    event.add('dtstart', start_time)
    event.add('dtend', end_time)
    event.add('categories', entry_type)
    cal.add_component(event)

    try:
        with open(ics_file_path, 'wb') as file:
            file.write(cal.to_ical())
        return True  # Indicate success
    except Exception as e:
        print(f"Error writing to calendar file: {e}")
        return False  # Indicate failure

def play_music(music_dirs):
    global vlc_player
    all_music_files = []
    for music_dir in music_dirs:
        if os.path.exists(music_dir):
            all_music_files.extend([os.path.join(music_dir, f) for f in os.listdir(music_dir) if f.endswith(('.mp3', '.mp4'))])
        else:
            print(f"Warning: Directory not found: {music_dir}")
    if all_music_files:
        random_file = random.choice(all_music_files)
        vlc_player = vlc.MediaPlayer(random_file)
        vlc_player.play()
        return f"Now playing: {os.path.basename(random_file)}"
    else:
        return "No music files found in the specified directories."

def play_youtube_audio(query):
    global vlc_player
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            url = info['url']
            title = info['title']
            vlc_player = vlc.MediaPlayer(url)
            vlc_player.play()
            return f"Now playing: {title}"
        except Exception as e:
            print(f"Error playing YouTube audio: {e}")
            return f"Could not play {query} from YouTube."

async def chat_with_ollama(prompt):
    client = Client(host='http://localhost:11434')
    response = client.chat(model='tinyllama', messages=[
        {
            'role': 'user',
            'content': prompt,
        },
    ])
    return response['message']['content']

class TTSEngine:
    def __init__(self, voice="en_US-danny-low"):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def speak(self, text):
        try:
            # Suppress aplay output by redirecting both stderr and stdout to /dev/null
            subprocess.run(['aplay', '-'], input=self.dt.text_2_speech(text, engine="return").encode('utf-8'), stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except Exception as e:
            print(f"TTS Error: {e}")
            print(f"Falling back to text output: {text}")

    def set_voice(self, voice):
        self.voice = voice
        self.dt = Dimits(self.voice)

    def list_voices(self):
        try:
            voices = Dimits.list_voices()
            print("Available voices:")
            for voice in voices:
                print(voice)
        except Exception as e:
            print(f"Error listing voices: {e}")

def get_intent(text):
    doc = nlp(text)
    intents = {
        "add_entry": ["add", "create", "new", "schedule", "set up"],
        "play_music": ["play", "music", "song", "tune"],
        "youtube": ["youtube", "search youtube", "play on youtube", "watch", "video"],
        "chat": ["chat", "talk", "converse", "speak", "tell me"],
        "exit": ["exit", "quit", "bye", "goodbye", "stop"],
        "weather": ["weather", "temperature", "forecast", "climate"],
        "schedule": ["schedule", "events", "calendar", "agenda", "meetings"],
        "memo": ["memo", "voice memo", "record", "note"],
        "time": ["time", "clock", "what time is it"],
        "date": ["date", "day", "today", "what day is it"],
        "news": ["news", "latest news", "headlines", "updates"],
        "reminder": ["remind", "set reminder", "alarm"],
        "search": ["search", "look up", "find"],
    }
    for intent, keywords in intents.items():
        if any(keyword in text.lower() for keyword in keywords):
            return intent
    return "unknown"

async def handle_weather_intent(tts, location):
    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

async def handle_schedule_intent(tts, ics_file_path):
    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

def handle_time_intent(tts):
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}")
    tts.speak(f"The current time is {current_time}")

def handle_date_intent(tts):
    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

# news functionality
async def handle_news_intent(tts):
    print("Fetching the latest news...")
    tts.speak("Fetching the latest news...")

    # List of RSS feeds from various news sources
    rss_feeds = [
        "http://rss.cnn.com/rss/cnn_topstories.rss",
        "https://feeds.bbci.co.uk/news/rss.xml",
        "http://feeds.reuters.com/reuters/topNews",
    ]

    # Choose a random feed
    feed_url = random.choice(rss_feeds)
    
    # Parse the feed
    feed = feedparser.parse(feed_url)
    
    if feed.entries:
        # Get the latest news item
        latest_news = feed.entries[0]
        news_content = f"Latest news: {latest_news.title}. {latest_news.summary}"
    else:
        news_content = "Sorry, I couldn't fetch the latest news at the moment."

    print(news_content)
    tts.speak(news_content)

reminders = []
# reminder functionality
async def check_reminders(tts):
    global reminders
    while True:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        for reminder in reminders:
            if reminder["time"] == current_time:
                print(f"Reminder: {reminder['message']}")
                tts.speak(f"Reminder: {reminder['message']}")
                reminders.remove(reminder)
        await asyncio.sleep(60)  # Check every minute

async def handle_reminder_intent(tts):
    print("Setting a reminder...")
    tts.speak("Setting a reminder...")

    reminder_time_str = input("Enter the reminder time (YYYY-MM-DD HH:MM): ")
    reminder_message = input("Enter the reminder message: ")
    
    try:
        reminder_time = datetime.datetime.strptime(reminder_time_str, "%Y-%m-%d %H:%M")
        reminders.append({
            "time": reminder_time.strftime("%Y-%m-%d %H:%M"),
            "message": reminder_message
        })

        reminder_set_message = f"Reminder set for {reminder_time_str}: {reminder_message}"
        print(reminder_set_message)
        tts.speak(reminder_set_message)
    except ValueError:
        error_message = "Invalid date format. Please use YYYY-MM-DD HH:MM."
        print(error_message)
        tts.speak(error_message)

#  search functionality
async def handle_search_intent(tts, query):
    print(f"Searching for: {query}...")
    tts.speak(f"Searching for: {query}...")

    with DDGS() as ddgs:
        results = [r["title"] for r in ddgs.text(query, max_results=3)]

    search_results = ". ".join(results) if results else "No results found."
    print(search_results)
    tts.speak(search_results)

async def ai_assistant(tts):
    time_of_day = get_time_of_day()
    print(f"Good {time_of_day}!")
    tts.speak(f"Good {time_of_day}!")

    date = get_date()
    print(f"Today is {date}.")
    tts.speak(f"Today is {date}.")

    location = get_coordinates("New Haven, CT")
    ics_file_path = os.path.expanduser("~/.local/share/evolution/calendar/system/calendar.ics")

    weather = await get_weather(location)
    print(weather)
    tts.speak(weather)

    events = get_korganizer_events(ics_file_path)
    if events:
        print("Your schedule for today includes:")
        tts.speak("Your schedule for today includes:")
        for event in events:
            print(event)
            tts.speak(event)
    else:
        print("You have no events scheduled for today.")
        tts.speak("You have no events scheduled for today.")

    while True:
        print("I'm ready for your command.")
        tts.speak("I'm ready for your command.")
        command = input("Enter your command: ")
        intent = get_intent(command)

        if intent == "add_entry":
            summary = input("Enter the summary of the entry: ")
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(hours=1)
            entry_type = input("Enter the type of entry (todo, reminder, appointment): ")
            if add_ical_entry(ics_file_path, summary, start_time, end_time, entry_type):
                print(f"Added {entry_type} entry: {summary}")
                tts.speak(f"Added {entry_type} entry: {summary}")
            else:
                print("Failed to add calendar entry.")
                tts.speak("Failed to add calendar entry.")

        elif intent == "play_music":
            music_dirs = ["/home/sam/Music/", "/home/sam/Downloads/"]
            result = play_music(music_dirs)
            print(result)
            tts.speak(result)
        elif intent == "youtube":
            query = input("Enter the YouTube search query: ")
            result = play_youtube_audio(query)
            print(result)
            tts.speak(result)
        elif intent == "chat":
            prompt = input("Enter your message for the AI: ")
            response = await chat_with_ollama(prompt)
            print("AI response:", response)
            tts.speak(response)
        elif intent == "memo":
            # await voice_recording.VoiceRecording()
            print("Voice recording feature is temporarily disabled")
            tts.speak("Voice recording feature is temporarily disabled")
        elif intent == "weather":
            await handle_weather_intent(tts, location)
        elif intent == "schedule":
            await handle_schedule_intent(tts, ics_file_path)
        elif intent == "time":
            handle_time_intent(tts)
        elif intent == "date":
            handle_date_intent(tts)
        elif intent == "news":
            await handle_news_intent(tts)
        elif intent == "reminder":
            await handle_reminder_intent(tts)
        elif intent == "search":
            search_query = input("What do you want to search for? ")
            await handle_search_intent(tts, search_query)
        elif intent == "exit":
            print("Goodbye!")
            tts.speak("Goodbye!")
            break
        else:
            print("I'm sorry, I didn't understand that command.")
            tts.speak("I'm sorry, I didn't understand that command.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    tts = TTSEngine()
    asyncio.run(ai_assistant(tts))
