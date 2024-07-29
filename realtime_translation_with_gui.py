import pyaudio
import numpy as np
import tkinter as tk
from tkinter import ttk
import threading
import queue
import sounddevice as sd
import soundfile as sf
import os
from dotenv import load_dotenv
from google.cloud import speech
from google.oauth2 import service_account
import logging

# Очистка лог-файла при запуске
with open("app.log", "w", encoding="utf-8") as log_file:
    log_file.write("")

# Настройка логирования с кодировкой utf-8
logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", encoding="utf-8")

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

# Загрузка переменных окружения из файла .env
load_dotenv()
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
print(f"Path to Google credentials: {credentials_path}")

# Инициализация клиента Google Cloud Speech-to-Text
credentials = service_account.Credentials.from_service_account_file(credentials_path)
client = speech.SpeechClient(credentials=credentials)

# Конфигурация распознавания
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=RATE,
    language_code="ru-RU",
    enable_automatic_punctuation=True
)

streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

def audio_generator():
    while recording.is_set():
        data = recording_buffer.pop(0) if recording_buffer else None
        if data:
            yield speech.StreamingRecognizeRequest(audio_content=data)

def process_responses(responses):
    global translation_text
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if result.is_final:
            final_transcript = result.alternatives[0].transcript
            translation_text.config(state=tk.NORMAL)
            translation_text.insert(tk.END, final_transcript + "\n")
            translation_text.config(state=tk.DISABLED)
            logging.info(f"Распознанный текст (конечный): {final_transcript}")
        else:
            interim_transcript = result.alternatives[0].transcript
            translation_text.config(state=tk.NORMAL)
            translation_text.delete("1.0", tk.END)
            translation_text.insert(tk.END, interim_transcript + "\n")
            translation_text.config(state=tk.DISABLED)
            logging.info(f"Распознанный текст (промежуточный): {interim_transcript}")

def record_audio():
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)
    while recording.is_set():
        data = stream.read(CHUNK)
        recording_buffer.append(data)
        if playing.is_set():
            playback_queue.put(data)
    stream.stop_stream()
    stream.close()

def start_recording():
    translation_text.config(state=tk.NORMAL)
    translation_text.delete(1.0, tk.END)
    translation_text.config(state=tk.DISABLED)
    recording.set()
    threading.Thread(target=record_audio, daemon=True).start()
    threading.Thread(target=streaming_recognize, daemon=True).start()

def stop_recording():
    recording.clear()

def streaming_recognize():
    responses = client.streaming_recognize(streaming_config, audio_generator())
    process_responses(responses)

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
