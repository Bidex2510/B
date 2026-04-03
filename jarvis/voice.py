"""Voice interaction - speech-to-text and text-to-speech."""

import speech_recognition as sr
import pyttsx3


class Voice:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self._configure_voice()

    def _configure_voice(self):
        voices = self.engine.getProperty("voices")
        # Try to find a male English voice (Jarvis-like)
        for voice in voices:
            if "english" in voice.name.lower() and "male" in voice.name.lower():
                self.engine.setProperty("voice", voice.id)
                break
        self.engine.setProperty("rate", 175)
        self.engine.setProperty("volume", 0.9)

    def speak(self, text: str):
        """Convert text to speech."""
        print(f"\n  Jarvis: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self) -> str | None:
        """Listen for voice input and convert to text."""
        with sr.Microphone() as source:
            print("\n  [Listening...]")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                text = self.recognizer.recognize_google(audio)
                print(f"  You: {text}")
                return text
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                print("  [Couldn't understand that]")
                return None
            except sr.RequestError as e:
                print(f"  [Speech recognition error: {e}]")
                return None


class TextFallback:
    """Fallback when voice hardware isn't available."""

    def speak(self, text: str):
        print(f"\n  Jarvis: {text}")

    def listen(self) -> str | None:
        try:
            return input("\n  You: ").strip() or None
        except (EOFError, KeyboardInterrupt):
            return None
