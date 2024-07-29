import pyaudio
import numpy as np
import tkinter as tk
from tkinter import ttk
import threading
import queue
import sounddevice as sd
import soundfile as sf
import os
import speech_recognition as sr
import logging
from google.cloud import speech
from google.oauth2 import service_account
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Очистка лог-файла при запуске
with open("app.log", "w", encoding="utf-8") as log_file:
    log_file.write("")

# Настройка логирования с кодировкой utf-8
logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s - %(levellevelname)s - %(message)s", encoding="utf-8")

# Параметры аудио
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024

# Инициализация PyAudio
audio = pyaudio.PyAudio()

# Буферы для аудио данных
recording_buffer = []
playback_queue = queue.Queue()

# Флаги для управления потоками
recording = threading.Event()
playing = threading.Event()

recognizer = sr.Recognizer()

# Загрузка учетных данных Google Cloud
google_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
print(f"Path to Google credentials: {google_credentials_path}")
credentials = service_account.Credentials.from_service_account_file(google_credentials_path)
client = speech.SpeechClient(credentials=credentials)

# Конфигурация для распознавания речи
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=RATE,
    language_code="ru-RU",
)
streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

# Функция записи аудио
def record_audio():
    def audio_generator():
        while recording.is_set():
            data = audio_stream.read(CHUNK)
            yield speech.StreamingRecognizeRequest(audio_content=data)
            recording_buffer.append(data)
            if playing.is_set():
                playback_queue.put(data)
        audio_stream.stop_stream()
        audio_stream.close()

    audio_stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    requests = audio_generator()

    responses = client.streaming_recognize(config=streaming_config, requests=requests)
    process_responses(responses)

def process_responses(responses):
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        if result.is_final:
            update_text(transcript)
            logging.info(f"Распознанный текст: {transcript}")
        else:
            update_text(transcript, interim=True)

def update_text(text, interim=False):
    translation_text.config(state=tk.NORMAL)
    if interim:
        translation_text.delete('1.0', tk.END)
        translation_text.insert(tk.END, text + "\n")
    else:
        translation_text.insert(tk.END, text + "\n")
    translation_text.config(state=tk.DISABLED)

# Функция воспроизведения аудио
def play_audio():
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True)
    while playing.is_set():
        if not playback_queue.empty():
            data = playback_queue.get()
            stream.write(data)
    stream.stop_stream()
    stream.close()

# Запуск записи аудио
def start_recording():
    translation_text.config(state=tk.NORMAL)
    translation_text.delete(1.0, tk.END)
    translation_text.config(state=tk.DISABLED)
    recording.set()
    threading.Thread(target=record_audio, daemon=True).start()

# Остановка записи аудио
def stop_recording():
    recording.clear()

# Запуск воспроизведения аудио
def start_playing():
    playback_queue.queue.clear()  # Очистка очереди перед воспроизведением
    for data in recording_buffer:
        playback_queue.put(data)
    playing.set()
    threading.Thread(target=play_audio, daemon=True).start()

# Остановка воспроизведения аудио
def stop_playing():
    playing.clear()

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
ttk.Button(root, text="Воспроизвести запись", command=start_playing).grid(column=0, row=4, padx=10, pady=10)
ttk.Button(root, text="Остановить воспроизведение", command=stop_playing).grid(column=1, row=4, padx=10, pady=10)

root.mainloop()

# Освобождение ресурсов PyAudio при завершении работы
audio.terminate()
