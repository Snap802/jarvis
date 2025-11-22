import vosk, pyaudio, json
model = vosk.Model("D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15")
rec = vosk.KaldiRecognizer(model, 16000)
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, input_device_index=1, frames_per_buffer=8000)
stream.start_stream()

print("🎤 Speak now... (say something for 5 seconds)")
for i in range(600):
    data = stream.read(4000, exception_on_overflow=False)
    if rec.AcceptWaveform(data):
        result = rec.Result()
        print(json.loads(result)["text"])

stream.stop_stream()
stream.close()
p.terminate()
