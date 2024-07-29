import pyaudio
import tkinter as tk
from tkinter import ttk
import threading
import queue
import os
import logging
from google.cloud import speech_v1p1beta1 as speech
from google.oauth2 import service_account
from google.auth.exceptions import DefaultCredentialsError
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Инициализация логирования
with open("app.log", "w", encoding="utf-8") as log_file:
    log_file.write("")

logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
                    encoding="utf-8")

# Загрузка учетных данных из переменной окружения
try:
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"Path to Google credentials: {credentials_path}")
    if not credentials_path:
        raise ValueError("Path to Google credentials not found in environment variables.")
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    client = speech.SpeechClient(credentials=credentials)
except (DefaultCredentialsError, ValueError) as e:
    logging.error(f"Google credentials error: {e}")
    raise

# Параметры аудио
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024

# Инициализация PyAudio
audio = pyaudio.PyAudio()

# Буферы для аудио данных
recording_buffer = queue.Queue()

# Флаги для управления потоками
recording = threading.Event()

# Конфигурация распознавания
language_code = "ru-RU"
last_transcript = ""


# Функция записи аудио
def record_audio():
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    audio_generator = (stream.read(CHUNK) for _ in iter(int, 1))

    config = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, sample_rate_hertz=RATE,
                                      language_code=language_code)
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

    try:
        requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
        responses = client.streaming_recognize(streaming_config, requests)

        for response in responses:
            process_responses(response)
    except Exception as e:
        logging.error(f"Error during streaming recognition: {e}")
    finally:
        stream.stop_stream()
        stream.close()


def process_responses(response):
    global last_transcript
    for result in response.results:
        if not result.is_final:
            continue
        transcript = result.alternatives[0].transcript
        if transcript != last_transcript:
            last_transcript = transcript
            update_text(transcript)
            logging.info(f"Распознанный текст: {transcript}")


def update_text(text):
    translation_text.config(state=tk.NORMAL)
    translation_text.insert(tk.END, text + "\n")
    translation_text.config(state=tk.DISABLED)


# Функция для запуска записи аудио
def start_recording():
    translation_text.config(state=tk.NORMAL)
    translation_text.delete(1.0, tk.END)
    translation_text.config(state=tk.DISABLED)
    recording.set()
    threading.Thread(target=record_audio, daemon=True).start()


# Функция для остановки записи аудио
def stop_recording():
    recording.clear()


# Инициализация GUI
root = tk.Tk()
root.title("Захват аудио")

ttk.Label(root, text="Чувствительность микрофона:").grid(column=0, row=0, padx=10, pady=10, sticky='W')
mic_sensitivity = tk.Scale(root, from_=0, to=100, orient=tk.HORIZONTAL)
mic_sensitivity.set(50)
mic_sensitivity.grid(column=1, row=0, padx=10, pady=10, sticky='W')

ttk.Label(root, text="Выберите язык распознавания:").grid(column=0, row=1, padx=10, pady=10, sticky='W')
language_var = tk.StringVar()
language_combobox = ttk.Combobox(root, textvariable=language_var, values=["ru-RU", "en-US", "nl-NL"])
language_combobox.grid(column=1, row=1, padx=10, pady=10, sticky='W')
language_combobox.current(0)

translation_text = tk.Text(root, wrap=tk.WORD, state=tk.DISABLED)
translation_text.grid(column=0, row=2, columnspan=2, padx=10, pady=10, sticky='W')

ttk.Button(root, text="Начать запись", command=start_recording).grid(column=0, row=3, padx=10, pady=10)
ttk.Button(root, text="Остановить запись", command=stop_recording).grid(column=1, row=3, padx=10, pady=10)

root.mainloop()

# Освобождение ресурсов PyAudio при завершении работы
audio.terminate()
