import speech_recognition as sr
import pyttsx3
import time
import webbrowser
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
import subprocess
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the browser driver
driver = None

# create a speech recognition object
r = sr.Recognizer()
r.energy_threshold = 5000  # mic sensitivity adjustment

# Initialize the speech synthesis engine
engine = pyttsx3.init()

# Choose a voice
voices = engine.getProperty('voices')
for index, voice in enumerate(voices):
    if "english" in voice.languages and "David" in voice.gender.lower():
        selected_voice = voice
        break
else:
    selected_voice = voices[0]  # fallback to the first voice if no english male voice is found

engine.setProperty('voice', selected_voice.id)

# Adjust rate of speech
rate = engine.getProperty('rate')  # getting details of current speaking rate
engine.setProperty('rate', rate - 50)  # reducing the rate of speech

# Adjust volume
volume = engine.getProperty('volume')  # getting to know current volume level (min=0 and max=1)
engine.setProperty('volume', volume + 0.25)  # increasing the volume

# Spotify credentials
spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

redirect_uri = 'http://localhost:8000/callback'

# Spotify client credentials manager
spotify_credentials_manager = SpotifyClientCredentials(client_id=spotify_client_id,
                                                       client_secret=spotify_client_secret)

# Spotify API object
spotify = spotipy.Spotify(client_credentials_manager=spotify_credentials_manager,
                          auth_manager=SpotifyOAuth(client_id=spotify_client_id,
                                                   client_secret=spotify_client_secret,
                                                   redirect_uri=redirect_uri,
                                                   scope=['user-modify-playback-state', 'user-read-playback-state']))



def start_browser():
    # Setup Chrome options
    options = webdriver.ChromeOptions()

    # Set the binary location based on the default browser
    options.binary_location = webbrowser.get().name  # Use the default browser path

    # Create a new instance of the browser driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

            
def speak(text):
    engine.say(text)
    engine.runAndWait()


# function to recognize command from the microphone
def recognize_command():
    with sr.Microphone() as source:
        print("Listening for command...")
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=10)  # Set a timeout of 10 seconds
        except sr.WaitTimeoutError:
            return
        try:
            command = r.recognize_google(audio)
            print(f"You said: {command}")
            return command
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand your audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")


# function to recognize wake word from the microphone
def recognize_wake_word():
    with sr.Microphone() as source:
        print("Listening for wake word...")
        r.adjust_for_ambient_noise(source)

        try:
            audio = r.listen(source, timeout=10)  # Set a timeout of 10 seconds
        except sr.WaitTimeoutError:
            return

        try:
            speech = r.recognize_google(audio)
            print(f"You said: {speech}")
            return speech
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand your audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")


def monitor_protocol():
    driver.get('http://192.168.1.102/admin/')
    wait = WebDriverWait(driver, 5)
    speak("Hold on sir while I'm logging you in!")
    try:
        # Try to locate the password input field
        password_field = wait.until(EC.presence_of_element_located((By.ID, 'loginpw')))
        # If the password field is found, type the password into the password field
        password = os.getenv('PiHolePassword')
        password_field.send_keys(password)
        # Locate the "Log in" button and click it
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]')))
        login_button.click()
    except TimeoutException:
        # If the password field is not found within the given wait time, print a message
        speak("Look Like you're already logged in!")





def search_youtube(term):
    # Check if we're already on YouTube
    current_url = driver.current_url
    if 'https://www.youtube.com' not in current_url:
        # Navigate to YouTube
        driver.get('https://www.youtube.com/')

    wait = WebDriverWait(driver, 20)  # Increasing wait time to 20 seconds

    try:
        # Wait until the search box is present and clickable, input the search term, and submit
        search_box = wait.until(EC.element_to_be_clickable((By.NAME, 'search_query')))
        search_box.clear()
        search_box.send_keys(term)
        search_box.send_keys(Keys.RETURN)

        # wait 2 seconds for page to load
        time.sleep(1)

        # Wait for search results to load and then click on the first video
        first_video = wait.until(EC.presence_of_element_located((By.XPATH, '(//ytd-video-renderer//a[@id="thumbnail"])[1]')))
        first_video.click()

    except TimeoutException:
        speak("Search took too long!")
    except Exception as e:
        speak(f"An error occurred")
        raise e

def search_spotify():
    while True:
        speak("What would you like to search for on Spotify?")
        search_term = recognize_command()
        search_term = search_term.lower()
        
        if not search_term:
            print("Please enter a valid search term.")
            continue

        try:
            results = spotify.search(q=search_term, type='track', limit=1)
            break
        except Exception as e:
            print(e)
            print("An error occurred while searching Spotify. Please try again.")

    if results and 'tracks' in results and results['tracks']['items']:
        track = results['tracks']['items'][0]
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        speak(f"I found a track on Spotify. The track is '{track_name}' by '{artist_name}'.")
        track_uri = track['uri']
        play_on_spotify(track_uri)
    else:
        speak("No tracks found on Spotify for the given search term.")

def search_album_spotify():
    while True:
        speak("What album would you like to search on Spotify?")
        search_term = recognize_command()
        if not search_term:
            speak("Please try again.")
            continue

        try:
            results = spotify.search(q=search_term, type='album', limit=1)
            break
        except Exception as e:
            print(e)
            speak("An error occurred while searching Spotify. Please try again.")
            return

    if results and 'albums' in results and results['albums']['items']:
        album = results['albums']['items'][0]
        album_name = album['name']
        speak(f"I found an album on Spotify. The album is '{album_name}'.")
        album_uri = album['uri']
        play_album_on_spotify(album_uri)  # Call the new play_album_on_spotify function
    else:
        speak("No albums found on Spotify for the given search term.")



def play_album_on_spotify(album_uri):
    # Check if Spotify application is running
    if not is_spotify_running():
        try:
            speak("Starting Spotify...")
            if os.name == 'nt':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                subprocess.Popen(['C:\\Users\\Q\\AppData\\Roaming\\Spotify\\Spotify.exe'], creationflags=creation_flags)  # Replace with the actual path to Spotify.exe
            else:
                subprocess.Popen(['spotify'], preexec_fn=os.setsid)
            time.sleep(5)  # Wait for Spotify to start
        except Exception:
            speak("Failed to start Spotify.")
            return
    
    # Check if any active devices are available
    devices = spotify.devices()
    if not devices['devices']:
        speak("No active devices found. Please ensure that a device is active and connected to Spotify.")
        return

    # Select the first active device
    device_id = devices['devices'][0]['id']

    # Transfer playback to the selected device
    spotify.transfer_playback(device_id=device_id)

    time.sleep(1)
    
    try:
        # Get album tracks
        album_tracks = spotify.album_tracks(album_uri)

        # Extract track URIs
        track_uris = [track['uri'] for track in album_tracks['items']]
        
        # Play the tracks on Spotify
        spotify.start_playback(uris=track_uris)
    except Exception:
        speak("an error has occurred")
        return


def search_playlist_spotify():
    while True:
        speak("What playlist would you like to search on Spotify?")
        search_term = recognize_command()
        if not search_term:
            speak("Please try again.")
            continue

        try:
            results = spotify.search(q=search_term, type='playlist', limit=1)
            break
        except Exception as e:
            print(e)
            speak("An error occurred while searching Spotify. Please try again.")
            return

    if results and 'playlists' in results and results['playlists']['items']:
        playlist = results['playlists']['items'][0]
        playlist_name = playlist['name']
        speak(f"I found a playlist on Spotify. The playlist is '{playlist_name}'.")
        playlist_uri = playlist['uri']
        play_playlist_on_spotify(playlist_uri)
    else:
        speak("No playlists found on Spotify for the given search term.")
        
def play_playlist_on_spotify(playlist_uri):
    # Check if Spotify application is running
    if not is_spotify_running():
        try:
            speak("Starting Spotify...")
            if os.name == 'nt':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                subprocess.Popen(['C:\\Users\\Q\\AppData\\Roaming\\Spotify\\Spotify.exe'], creationflags=creation_flags)  # Replace with the actual path to Spotify.exe
            else:
                subprocess.Popen(['spotify'], preexec_fn=os.setsid)
            time.sleep(5)  # Wait for Spotify to start
        except Exception:
            speak("Failed to start Spotify.")
            return
    
    # Check if any active devices are available
    devices = spotify.devices()
    if not devices['devices']:
        speak("No active devices found. Please ensure that a device is active and connected to Spotify.")
        return

    # Select the first active device
    device_id = devices['devices'][0]['id']

    # Transfer playback to the selected device
    spotify.transfer_playback(device_id=device_id)

    time.sleep(1)
    
    try:
        # Get playlist tracks
        playlist_tracks = spotify.playlist_tracks(playlist_uri)

        # Extract track URIs
        track_uris = [track['track']['uri'] for track in playlist_tracks['items']]
        
        # Play the tracks on Spotify
        spotify.start_playback(uris=track_uris)
    except Exception:
        speak("An error has occurred")
        return



def play_on_spotify(track_uri):
    # Check if Spotify application is running
    if not is_spotify_running():
        try:
            speak("Starting Spotify...")
            if os.name == 'nt':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                subprocess.Popen(['C:\\Users\\Q\\AppData\\Roaming\\Spotify\\Spotify.exe'], creationflags=creation_flags)  # Replace with the actual path to Spotify.exe
            else:
                subprocess.Popen(['spotify'], preexec_fn=os.setsid)
            time.sleep(5)  # Wait for Spotify to start
        except Exception:
            speak("Failed to start Spotify.")
            return
    
    # Check if any active devices are available
    devices = spotify.devices()
    if not devices['devices']:
        speak("No active devices found. Please ensure that a device is active and connected to Spotify.")
        return

    # Select the first active device
    device_id = devices['devices'][0]['id']

    # Transfer playback to the selected device
    spotify.transfer_playback(device_id=device_id)

    time.sleep(1)
    
    try:
        # Play the track on Spotify
        spotify.start_playback(uris=[track_uri])
    except Exception:
        speak("an error has occurred")
        return

def is_spotify_running():
    # Get the list of running processes
    processes = subprocess.Popen(['tasklist'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True)

    # Check if "Spotify.exe" is in the list of processes
    return 'Spotify.exe' in processes.communicate()[0]

def close_spotify():
    if is_spotify_running():
        if os.name == 'nt':
            subprocess.Popen(['taskkill', '/f', '/im', 'Spotify.exe'])
        else:
            os.system("pkill Spotify")
        speak("Spotify is closed.")
    else:
        speak("Spotify is not running.")

def add_song_to_queue_spotify():
    while True:
        speak("What song would you like to add to the queue on Spotify?")
        search_term = recognize_command()
        if not search_term:
            speak("Please try again.")
            continue

        try:
            # Search for the song on Spotify
            results = spotify.search(q=search_term, type='track', limit=1)
            if results and 'tracks' in results and results['tracks']['items']:
                track = results['tracks']['items'][0]
                track_name = track['name']
                track_uri = track['uri']
                
                # Add the song to the queue
                spotify.add_to_queue(uri=track_uri)
                speak(f"I have added the song '{track_name}' to your Spotify queue.")
                break
            else:
                speak("No songs found on Spotify with the given name. Please try again.")
        except Exception as e:
            print(e)
            speak("An error occurred while trying to add the song to the queue on Spotify. Please try again.")
            continue


while True:
    wake_word = recognize_wake_word()
    wake_word_lower = wake_word.lower() if wake_word else ""
  
    
    if "jarvis" in wake_word_lower:
        speak("Jarvis Here. How Can I Assist You?")
        # loop for continuous command recognition
        while True:
            command = recognize_command()
            command_lower = command.lower() if command else ""

            # a simple command handler
            if 'hello' in command_lower:
                speak("Hello to you too!")
                continue
            elif 'how are you' in command_lower:
                speak("I am fine, thank you.")
                continue
            elif 'search youtube for' in command_lower:
                search_term = command_lower.replace('search youtube for', '').strip()
                if driver is None or not driver.window_handles:
                    driver = start_browser()
                search_youtube(search_term)
                continue
            elif "add song" in command_lower:
                add_song_to_queue_spotify()
                continue
            elif 'search song' in command_lower:
                search_spotify()
                continue
            elif 'search album' in command_lower:
                search_album_spotify()
                continue
            elif 'search playlist' in command_lower:
                search_playlist_spotify()
                continue
            elif 'monitor protocol' in command_lower:
                speak("Monitoring Protocol Commence...")
                if driver is None or not driver.window_handles:
                    driver = start_browser()
                monitor_protocol()
                continue
            elif 'next song' in command_lower:
                speak("Playing the next song on Spotify.")
                try:
                    spotify.next_track()
                except Exception:
                    speak("Error playing next song.")
                continue
            elif 'previous song' in command_lower:
                speak("Playing the previous song on Spotify.")
                try:
                    spotify.previous_track()
                except Exception:
                    speak("Error playing previous song.")
                continue
            elif 'resume spotify' in command_lower:
                speak("Resuming playback on Spotify.")
                spotify.start_playback()
                continue
            elif 'pause spotify' in command_lower:
                speak("Pausing Spotify.")
                spotify.pause_playback()
                continue
            elif 'close spotify' in command_lower:
                speak("Closing Spotify.")
                close_spotify()
                break
            elif 'exit' in command_lower:
                speak("Exiting the command recognition...")
                break
            elif 'close tab' in command_lower:
                speak("Closing the current tab...")
                driver.close()  # Selenium command to close the current tab
                continue
            elif 'go back' in command_lower:
                speak("Navigating back...")
                driver.back()  # Selenium command to go back in browser history
                continue
            elif 'go forward' in command_lower:
                speak("Navigating forward...")
                driver.forward()  # Selenium command to go forward in browser history
                continue
            elif "kill protocol" in command_lower:
                speak("Killing protocol commence...")
                driver.quit()  # Selenium command to quit the browser
                break
            elif command is None:
                continue
