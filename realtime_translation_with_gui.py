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

recognizer = sr.Recognizer()

# Функция записи аудио
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

# Функция воспроизведения аудио
def play_audio():
    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, output=True)
    while playing.is_set():
        if not playback_queue.empty():
            data = playback_queue.get()
            stream.write(data)
    stream.stop_stream()
    stream.close()

# Функция преобразования аудио в текст
def transcribe_audio():
    global translation_text
    audio_data = np.frombuffer(b''.join(recording_buffer), dtype=np.int16)
    sf.write("temp.wav", audio_data, RATE)
    with sr.AudioFile("temp.wav") as source:
        audio = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio, language=language_var.get())
            translation_text.config(state=tk.NORMAL)
            translation_text.insert(tk.END, text + "\n")
            translation_text.config(state=tk.DISABLED)
            logging.info(f"Распознанный текст: {text}")
        except sr.UnknownValueError:
            translation_text.config(state=tk.NORMAL)
            translation_text.insert(tk.END, "[Не удалось распознать речь]\n")
            translation_text.config(state=tk.DISABLED)
            logging.info("Не удалось распознать речь")
        except sr.RequestError as e:
            translation_text.config(state=tk.NORMAL)
            translation_text.insert(tk.END, "[Ошибка сервиса распознавания]\n")
            translation_text.config(state=tk.DISABLED)
            logging.error(f"Ошибка сервиса распознавания: {e}")

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
    transcribe_audio()

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
