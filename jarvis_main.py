# jarvis_main.py — Full integration of JARVIS GUI + backend

import threading
import time
import tkinter as tk

from jarvis_opt import (
    load_model,
    listen_once_optimized,
    query_ollama,
    speak,
    handle_action,
    list_all_mics,
)
from jarvis_gui import JarvisGUI


class JarvisController:
    def __init__(self, gui: JarvisGUI, mic_index=None):
        self.gui = gui
        self.mic_index = mic_index
        self.running = True
        load_model()  # preload vosk
        speak("Jarvis system online.")
        self.gui.set_idle()

    def run(self):
        """Main loop connecting GUI + backend"""
        while self.running:
            try:
                # Wait for user to press Enter before listening
                self.gui.set_idle()
                input("\n[Press Enter to speak] ")

                # Listening phase
                self.gui.root.after(0, self.gui.set_listening)
                user_text = listen_once_optimized(device_index=self.mic_index)
                if not user_text:
                    continue

                print(f"✓ You: {user_text}")
                lower_text = user_text.lower()

                # Exit condition
                if any(x in lower_text for x in ["exit", "quit", "shutdown", "goodbye"]):
                    self.gui.root.after(0, self.gui.set_idle)
                    speak("Goodbye, Neil.")
                    self.running = False
                    break

                # Handle whitelisted system commands
                if any(x in lower_text for x in ["notepad", "browser", "chrome", "list", "directory"]):
                    self.gui.root.after(0, self.gui.set_thinking)
                    handle_action(user_text)
                    continue

                # Thinking phase (LLM)
                self.gui.root.after(0, self.gui.set_thinking)
                prompt = (
                    "You are JARVIS, Neil's personal offline AI assistant. "
                    "Respond efficiently and naturally.\nUser: " + user_text + "\nJARVIS:"
                )
                response = query_ollama(prompt)

                # Speaking phase
                self.gui.root.after(0, self.gui.set_speaking)
                if len(response) > 250:
                    response = response[:250] + "..."
                speak(response)

                # Return to idle
                self.gui.root.after(0, self.gui.set_idle)

            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"[Error] {e}")
                speak("An error occurred.")
                self.gui.root.after(0, self.gui.set_idle)

        # Cleanup before exit
        self.gui.set_idle()
        speak("System offline.")
        time.sleep(1)
        self.gui.root.quit()


def main():
    print("=" * 60)
    print(" JARVIS — Full Offline Assistant ")
    print("=" * 60)

    print("Listing microphones...")
    working_mics = list_all_mics()
    if not working_mics:
        print("❌ No working microphones found.")
        input("Press Enter to exit...")
        return

    if len(working_mics) == 1:
        mic_idx = working_mics[0]
    else:
        print(f"Available mics: {working_mics}")
        choice = input(f"Select mic index (default {working_mics[0]}): ").strip()
        mic_idx = int(choice) if choice.isdigit() and int(choice) in working_mics else working_mics[0]

    print(f"Using microphone index: {mic_idx}\n")

    # Setup GUI
    root = tk.Tk()
    gui = JarvisGUI(root)

    # Start backend controller
    controller = JarvisController(gui, mic_index=mic_idx)
    backend_thread = threading.Thread(target=controller.run, daemon=True)
    backend_thread.start()

    # Start GUI mainloop
    root.mainloop()

    controller.running = False
    backend_thread.join(timeout=2)
    print("JARVIS terminated.")


if __name__ == "__main__":
    main()
