# jarvis_fixed_gui.py
# Fixed integration combining the working CLI approach with the GUI
# Key fixes:
# 1. Push-to-talk instead of continuous listening
# 2. Proper silence detection
# 3. Unified model configuration
# 4. Better status feedback
# 5. FIX 1: Re-enable listening after full cycle (STT -> LLM -> TTS)
# 6. FIX 2: Correctly switch back from HUD to Combined mode
# 7. FIX 3: Added 'Hear Again' button for TTS playback

import threading, time, queue, os, json
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import requests
import moderngl
import pyttsx3
import pyaudio
from vosk import Model, KaldiRecognizer
import sys # <-- ADDED FOR PYINSTALLER

# --- START: ADDED FOR PYINSTALLER ---
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".") # Standard dev path

    return os.path.join(base_path, relative_path)
# --- END: ADDED FOR PYINSTALLER ---


# ---------------- CONFIG ----------------
# Use the SAME model as your working CLI version

# --- START: MODIFIED FOR PYINSTALLER ---
# VOSK_MODEL_PATH = "D:/Jarvis/models/vosk/vosk-model-small-en-us-0.15" # <-- OLD
VOSK_MODEL_DIR_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_PATH = get_resource_path(VOSK_MODEL_DIR_NAME)
# --- END: MODIFIED FOR PYINSTALLER ---

OLLAMA_API = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral:7b"  # Same as CLI

# Audio settings (match CLI)
CHUNK = 4096
RATE = 16000
CHANNELS = 1
LISTEN_TIMEOUT = 8

# Render settings
RENDER_W = 512
RENDER_H = 512
FPS = 30

# ---------------- Shared state ----------------
frame_queue = queue.Queue(maxsize=2)
transcript_queue = queue.Queue()
reply_queue = queue.Queue()
control_state = {
    'intensity': 0.0,
    'hue_offset': 0.0,
    'user_text': "",
    'jarvis_text': "",
    'is_listening': False,
    'lock': threading.Lock()
}

# ---------------- Shaders ----------------
VERTEX_SHADER = '''
#version 330
in vec2 in_pos;
void main() { gl_Position = vec4(in_pos.xy, 0.0, 1.0); }
'''

FRAGMENT_SHADER = r'''
#version 330
uniform vec2 resolution;
uniform float time;
uniform float intensity;
uniform float hue_offset;
out vec4 fragColor;

vec3 mod289(vec3 x){ return x - floor(x * (1.0/289.0)) * 289.0; }
vec4 mod289(vec4 x){ return x - floor(x * (1.0/289.0)) * 289.0; }
vec4 permute(vec4 x){ return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r){ return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v){
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i  = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min( g.xyz, l.zxy );
    vec3 i2 = max( g.xyz, l.zxy );
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute( permute( permute(
                         i.z + vec4(0.0, i1.z, i2.z, 1.0))
                       + i.y + vec4(0.0, i1.y, i2.y, 1.0))
                       + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 1.0/7.0;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4( x.xy, y.xy );
    vec4 b1 = vec4( x.zw, y.zw );
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 g0 = vec3(a0.x, a0.y, h.x);
    vec3 g1 = vec3(a0.z, a0.w, h.y);
    vec3 g2 = vec3(a1.x, a1.y, h.z);
    vec3 g3 = vec3(a1.z, a1.w, h.w);
    vec4 norm = taylorInvSqrt(
        vec4(dot(g0,g0), dot(g1,g1), dot(g2,g2), dot(g3,g3))
    );
    g0 *= norm.x; g1 *= norm.y; g2 *= norm.z; g3 *= norm.w;
    float m0 = max(0.6 - dot(x0,x0), 0.0);
    float m1 = max(0.6 - dot(x1,x1), 0.0);
    float m2 = max(0.6 - dot(x2,x2), 0.0);
    float m3 = max(0.6 - dot(x3,x3), 0.0);
    m0 = m0*m0; m1 = m1*m1; m2 = m2*m2; m3 = m3*m3;
    return 42.0 * (
        m0 * dot(g0,x0) + m1 * dot(g1,x1) + 
        m2 * dot(g2,x2) + m3 * dot(g3,x3)
    );
}

vec3 hsv2rgb(vec3 c){
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main(){
    vec2 uv = (gl_FragCoord.xy - 0.5 * resolution.xy) / resolution.y * 1.6;
    float d = length(uv);
    float t = time;

    float n = 0.0;
    float amp = 1.0;
    float freq = 1.0;
    for(int i = 0; i < 4; i++){
        n += amp * snoise(vec3(uv * freq * (1.0 + 0.25*intensity), 
                               t * (0.4 + 0.8*intensity) + float(i)*12.3));
        amp *= 0.5;
        freq *= 2.0;
    }
    n = (n + 1.0) * 0.5;

    // Core
    float core_hard = smoothstep(0.25, 0.05, d);
    float core_glow = smoothstep(0.55, 0.12, d);
    float pulse = 0.5 + 0.5 * sin(t * 3.0 + n * 6.0);
    float core = core_hard * 1.9 + core_glow * 0.8;
    core *= (0.7 + 0.3 * pulse);

    float hue = fract(0.55 + 0.05*sin(time*0.08) + hue_offset);
    vec3 core_col = hsv2rgb(vec3(hue + 0.02, 0.9, 1.4));

    // Shell
    float radial = exp(-d * (1.4 - 0.4 * intensity));
    float wobble = snoise(vec3(uv*1.4, t*0.6)) * 0.22 * intensity;
    float shell = smoothstep(0.25 + wobble, 0.75 + wobble, n) * radial;

    float veins = snoise(vec3(uv*7.5, t*2.3)) * 0.5 + 0.5;
    veins = smoothstep(0.6, 0.93, veins) * shell;

    vec3 col1 = hsv2rgb(vec3(hue, 0.85, 0.95));
    vec3 col2 = hsv2rgb(vec3(hue + 0.05, 0.95, 1.1));

    vec3 color = vec3(0.0);
    color += core_col * core * 2.0;
    color += col1 * shell * 1.2;
    color += col2 * veins * 1.3;
    float outer = smoothstep(1.5, 0.6, d);
    color += col1 * outer * 0.25;
    color = color / (color + vec3(1.0));
    color = pow(color, vec3(0.92));
    float alpha = clamp(core * 0.9 + shell * 0.5, 0.0, 1.0);
    fragColor = vec4(color, alpha);
}
'''

# ---------------- GL Worker ----------------
class GLWorker(threading.Thread):
    def __init__(self, frame_q, ctrl_state):
        super().__init__(daemon=True)
        self.frame_q = frame_q
        self.ctrl = ctrl_state
        self.running = True

    def run(self):
        try:
            ctx = moderngl.create_standalone_context(require=330)
        except Exception as e:
            print("ModernGL error:", e)
            return

        prog = ctx.program(vertex_shader=VERTEX_SHADER, fragment_shader=FRAGMENT_SHADER)
        verts = np.array([
            -1.0, -1.0, 1.0, -1.0, 1.0, 1.0,
            -1.0, -1.0, 1.0, 1.0, -1.0, 1.0,
        ], dtype='f4')
        vbo = ctx.buffer(verts.tobytes())
        vao = ctx.vertex_array(prog, [(vbo, '2f', 'in_pos')])

        tex = ctx.texture((RENDER_W, RENDER_H), 4)
        fbo = ctx.framebuffer(color_attachments=[tex])
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)

        start = time.time()
        frame_time = 1.0 / FPS

        while self.running:
            tnow = time.time()
            elapsed = tnow - start

            with self.ctrl['lock']:
                intensity = float(self.ctrl['intensity'])
                hue = float(self.ctrl['hue_offset'])

            fbo.use()
            ctx.viewport = (0, 0, RENDER_W, RENDER_H)
            ctx.clear(0.0, 0.0, 0.0, 0.0)
            
            prog['resolution'].value = (float(RENDER_W), float(RENDER_H))
            prog['time'].value = float(elapsed)
            prog['intensity'].value = float(intensity)
            prog['hue_offset'].value = float(hue)
            
            vao.render()
            data = fbo.read(components=4, alignment=1)
            img = Image.frombytes('RGBA', (RENDER_W, RENDER_H), data)
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

            try:
                if self.frame_q.qsize() >= 2:
                    _ = self.frame_q.get_nowait()
            except:
                pass
            try:
                self.frame_q.put_nowait(img)
            except:
                pass

            dt = time.time() - tnow
            sleep_time = frame_time - dt
            if sleep_time > 0:
                time.sleep(sleep_time)

        fbo.release()
        tex.release()
        vbo.release()
        vao.release()
        prog.release()

    def stop(self):
        self.running = False

# ---------------- STT Worker (CLI-style) ----------------
class STTWorker(threading.Thread):
    def __init__(self, transcript_q, control_state, model_path):
        super().__init__(daemon=True)
        self.transcript_q = transcript_q
        self.ctrl = control_state
        self.model_path = model_path
        self.running = True
        self.model = None

    def run(self):
        if not os.path.isdir(self.model_path):
            print(f"Model not found: {self.model_path}")
            # Add this print to help debug the PyInstaller path
            print(f"DEBUG: Failed to find model at path: {self.model_path}")
            return

        try:
            print(f"Loading Vosk model from: {self.model_path}")
            self.model = Model(self.model_path)
            print("✓ Model loaded")
        except Exception as e:
            print(f"Model load error: {e}")
            return

        # Listen loop waits for trigger
        while self.running:
            with self.ctrl['lock']:
                should_listen = self.ctrl['is_listening']
            
            if should_listen:
                text = self._listen_once()
                if text:
                    self.transcript_q.put_nowait(text)
                
                # Reset listening flag AFTER we're done
                with self.ctrl['lock']:
                    self.ctrl['is_listening'] = False
                
                print("✓ Ready for next command")
            
            time.sleep(0.1)

    def _listen_once(self):
        """CLI-style listening with silence detection"""
        p = pyaudio.PyAudio()
        
        # Find working mic
        device_index = None
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    test_stream = p.open(
                        format=pyaudio.paInt16, channels=1, rate=RATE,
                        input=True, frames_per_buffer=CHUNK, input_device_index=i
                    )
                    test_stream.close()
                    device_index = i
                    break
            except:
                continue
        
        if device_index is None:
            print("No working microphone")
            p.terminate()
            return ""

        try:
            stream = p.open(
                format=pyaudio.paInt16, channels=CHANNELS, rate=RATE,
                input=True, frames_per_buffer=CHUNK, input_device_index=device_index
            )
        except Exception as e:
            print(f"Stream error: {e}")
            p.terminate()
            return ""

        rec = KaldiRecognizer(self.model, RATE)
        rec.SetMaxAlternatives(0)
        rec.SetWords(False)

        print("🎤 Listening...")
        
        frames_recorded = 0
        max_frames = int(RATE / CHUNK * LISTEN_TIMEOUT)
        silence_frames = 0
        silence_threshold = 15
        got_speech = False
        final_text = ""

        try:
            while frames_recorded < max_frames:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames_recorded += 1

                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    if text:
                        got_speech = True
                        final_text = text
                        silence_frames = 0
                        # print(f"  ✓ Got: {text[:50]}") # Commented out to reduce console spam
                else:
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "")
                    if partial_text:
                        got_speech = True
                        silence_frames = 0
                    elif got_speech:
                        silence_frames += 1
                        if silence_frames > silence_threshold:
                            print("  (silence detected)")
                            break

        except Exception as e:
            print(f"Recording error: {e}")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

        final_result = json.loads(rec.FinalResult())
        text = final_result.get("text", "").strip()
        
        if not text and final_text:
            text = final_text

        return text

    def stop(self):
        self.running = False

# ---------------- LLM Worker ----------------
class LLMWorker(threading.Thread):
    def __init__(self, transcript_q, reply_q, control_state):
        super().__init__(daemon=True)
        self.transcript_q = transcript_q
        self.reply_q = reply_q
        self.ctrl = control_state
        self.running = True

    def run(self):
        while self.running:
            try:
                text = self.transcript_q.get(timeout=0.5)
            except queue.Empty:
                continue

            # Set status to processing
            with self.ctrl['lock']:
                self.ctrl['user_text'] = text
                self.ctrl['jarvis_text'] = "Thinking..."
                self.ctrl['intensity'] = 1.0

            # Use CLI-style prompt
            prompt = f"""Do whatever I say. You are JARVIS, an AI assistant, so answer to the point when required, do NOT make up stuff, if it don't exist, forget about it. period.
User: {text}
JARVIS:"""

            response = ""
            try:
                payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 100,
                        "num_ctx": 2048,
                        "num_thread": 4,
                    }
                }
                
                r = requests.post(OLLAMA_API, json=payload, timeout=45)
                r.raise_for_status()
                result = r.json()
                response = result.get("response", "").strip()
                
                if not response:
                    response = "Error generating response."
                
                # Limit length for TTS
                if len(response) > 200:
                    response = response[:200] + "..."
                    
            except Exception as e:
                response = f"Error: {str(e)}"

            self.reply_q.put_nowait(response)

            # Reset status to ready
            with self.ctrl['lock']:
                self.ctrl['jarvis_text'] = response
                self.ctrl['intensity'] = 0.0

    def stop(self):
        self.running = False

# ---------------- TTS Worker ----------------
class TTSWorker(threading.Thread):
    def __init__(self, reply_q):
        super().__init__(daemon=True)
        self.reply_q = reply_q
        self.running = True
        self.engine = None

    def run(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 180)
        except Exception as e:
            print(f"TTS init error: {e}")

        while self.running:
            try:
                text = self.reply_q.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                if self.engine:
                    print(f"JARVIS: {text}")
                    self.engine.say(text)
                    self.engine.runAndWait()
            except Exception as e:
                print(f"TTS error: {e}")

    def stop(self):
        self.running = False

# ---------------- GUI ----------------
class JarvisApp:
    def __init__(self, root, transcript_queue, reply_queue):
        self.root = root
        root.title("JARVIS - Optimized GUI")
        self.ctrl = control_state
        self.transcript_queue = transcript_queue
        self.reply_queue = reply_queue

        # Layout
        self.main = ttk.Frame(root)
        self.main.pack(fill='both', expand=True, padx=6, pady=6)

        # Left panel
        left = ttk.Frame(self.main, width=280)
        left.pack(side='left', fill='y', padx=(0,8))
        self.left_panel = left # Store reference for toggling

        ttk.Label(left, text="JARVIS Controls", font=("Segoe UI", 12, "bold")).pack(pady=(6,8))

        # Big SPEAK button
        self.speak_btn = ttk.Button(left, text="🎤 HOLD TO SPEAK", command=self._start_listening)
        self.speak_btn.pack(fill='x', padx=6, pady=12)
        
        ttk.Label(left, text="Status:").pack(anchor='w', padx=6)
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(left, textvariable=self.status_var, foreground='green')
        self.status_label.pack(anchor='w', padx=6, pady=4)

        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=12)

        # Display User Input
        ttk.Label(left, text="You said:").pack(anchor='w', padx=6)
        user_frame = ttk.Frame(left)
        user_frame.pack(fill='x', padx=6, pady=4)
        self.user_text = tk.Text(user_frame, height=3, wrap='word')
        self.user_text.pack(side='left', fill='both', expand=True)
        
        # Send button for manual text input
        ttk.Button(user_frame, text="▶", width=3, command=self._send_manual_text).pack(side='right', padx=(4,0))

        # Display JARVIS Reply + Re-say Button
        ttk.Label(left, text="JARVIS replied:").pack(anchor='w', padx=6, pady=(8,0))
        jarvis_frame = ttk.Frame(left)
        jarvis_frame.pack(fill='x', padx=6, pady=4)
        
        self.jarvis_text = tk.Text(jarvis_frame, height=4, wrap='word')
        self.jarvis_text.pack(side='left', fill='both', expand=True)
        
        # NEW: Hear Again Button
        ttk.Button(jarvis_frame, text="🔊", width=3, command=self._re_say_jarvis).pack(side='right', padx=(4,0))


        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=12)

        # Controls
        ttk.Label(left, text="Manual intensity").pack(anchor='w', padx=6)
        self.int_var = tk.DoubleVar(value=0.0)
        ttk.Scale(left, from_=0.0, to=1.0, variable=self.int_var, 
                 command=self._on_intensity).pack(fill='x', padx=6, pady=4)

        ttk.Label(left, text="Hue offset").pack(anchor='w', padx=6)
        self.hue_var = tk.DoubleVar(value=0.0)
        ttk.Scale(left, from_=0.0, to=1.0, variable=self.hue_var,
                 command=self._on_hue).pack(fill='x', padx=6, pady=4)

        ttk.Separator(left, orient='horizontal').pack(fill='x', pady=8)
        
        # Mode selector
        ttk.Label(left, text="Display Mode:").pack(anchor='w', padx=6)
        self.mode_var = tk.StringVar(value="combined")
        mode_frame = ttk.Frame(left)
        mode_frame.pack(fill='x', padx=6, pady=4)
        ttk.Radiobutton(mode_frame, text="Combined", variable=self.mode_var, 
                       value="combined", command=self._change_mode).pack(anchor='w')
        ttk.Radiobutton(mode_frame, text="HUD Only", variable=self.mode_var,
                       value="hud_only", command=self._change_mode).pack(anchor='w')

        ttk.Button(left, text="Quit", command=self._quit).pack(fill='x', padx=6, pady=8)

        # Right panel - HUD
        right = ttk.Frame(self.main)
        right.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(right, width=RENDER_W, height=RENDER_H, 
                               bg='black', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        # Start workers
        self.gl_worker = GLWorker(frame_queue, self.ctrl)
        self.gl_worker.start()

        self.stt = STTWorker(transcript_queue, self.ctrl, VOSK_MODEL_PATH)
        self.stt.start()

        self.llm = LLMWorker(transcript_queue, reply_queue, self.ctrl)
        self.llm.start()

        self.tts = TTSWorker(reply_queue)
        self.tts.start()

        self._photo = None
        
        self._poll_frames()
        self._poll_state()

    def _send_manual_text(self):
        """Send text from textbox manually without speech"""
        text = self.user_text.get('1.0', 'end').strip()
        if not text:
            return
        
        # Put directly into transcript queue to trigger LLM
        self.transcript_queue.put_nowait(text)
        self.status_var.set("Processing...")
        self.status_label.config(foreground='orange')

    def _re_say_jarvis(self):
        """Pushes the current JARVIS reply text back into the TTS queue."""
        text = self.jarvis_text.get('1.0', 'end').strip()
        if not text or text == "Thinking..." or text.startswith("Error"):
            return
        
        # Put directly into the reply queue to trigger TTS worker
        self.reply_queue.put_nowait(text)
        self.status_var.set("🔊 Speaking...")
        self.status_label.config(foreground='blue')

    def _change_mode(self):
        """Toggle between combined and HUD-only mode (FIX 2)"""
        mode = self.mode_var.get()
        if mode == "hud_only":
            self.left_panel.pack_forget()
            self.root.title("JARVIS - HUD Only")
            self.root.geometry("") # Allow window to shrink to fit HUD
        else:
            # Repack the left panel on the left side
            self.left_panel.pack(side='left', fill='y', padx=(0,8))
            self.left_panel.lift()
            self.root.title("JARVIS - Optimized GUI")
            # Force window to recalculate size to fit both panels
            self.root.update_idletasks()
            self.root.geometry("")

    def _start_listening(self):
        with self.ctrl['lock']:
            is_listening = self.ctrl['is_listening']
        
        if is_listening:
            return  # Already listening
        
        # Trigger listening in background
        with self.ctrl['lock']:
            self.ctrl['is_listening'] = True
        
        self.status_var.set("🎤 Listening...")
        self.status_label.config(foreground='red')
        self.speak_btn.config(state='disabled')

    def _poll_state(self):
        """Update UI from control state (FIX 1)"""
        with self.ctrl['lock']:
            user = self.ctrl['user_text']
            jarvis = self.ctrl['jarvis_text']
            listening = self.ctrl['is_listening']

        # Only update if there's new content
        current_user = self.user_text.get('1.0', 'end').strip()
        if user and user != current_user:
            self.user_text.delete('1.0', 'end')
            self.user_text.insert('1.0', user)

        if jarvis:
            self.jarvis_text.delete('1.0', 'end')
            self.jarvis_text.insert('1.0', jarvis)

        # Re-enable speak button after processing completes
        is_processing = ("Thinking..." in jarvis)
        
        if self.status_var.get() == "🔊 Speaking...":
             # We assume TTS takes a moment, keep button disabled briefly
             pass
        elif not listening and not is_processing:
            if self.speak_btn['state'] == 'disabled':
                self.speak_btn.config(state='normal')
            
            # Reset status if it was in an active state
            if self.status_var.get() in ["🎤 Listening...", "Processing..."]:
                self.status_var.set("Ready")
                self.status_label.config(foreground='green')
            
        elif listening and self.status_var.get() != "🎤 Listening...":
            self.status_var.set("🎤 Listening...")
            self.status_label.config(foreground='red')

        self.root.after(100, self._poll_state)

    def _on_intensity(self, _=None):
        with self.ctrl['lock']:
            self.ctrl['intensity'] = float(self.int_var.get())

    def _on_hue(self, _=None):
        with self.ctrl['lock']:
            self.ctrl['hue_offset'] = float(self.hue_var.get())

    def _poll_frames(self):
        try:
            img = frame_queue.get_nowait()
            self._photo = ImageTk.PhotoImage(img.resize((RENDER_W, RENDER_H), Image.LANCZOS))
            self.canvas.delete("HUDIMG")
            self.canvas.create_image(RENDER_W//2, RENDER_H//2, image=self._photo, tags="HUDIMG")
        except queue.Empty:
            pass
        
        self.root.after(int(1000 / FPS), self._poll_frames)

    def _quit(self):
        self.gl_worker.stop()
        self.stt.stop()
        self.llm.stop()
        self.tts.stop()
        time.sleep(0.1)
        self.root.destroy()

# ---------------- Main ----------------
def main():
    if not os.path.isdir(VOSK_MODEL_PATH):
        print(f"ERROR: Vosk model not found at: {VOSK_MODEL_PATH}")
        print("Update VOSK_MODEL_PATH at the top of the script")
        # Add this print to help debug the PyInstaller path
        print(f"DEBUG: Failed to find model at path: {VOSK_MODEL_PATH}")
        return

    print("="*50)
    print("JARVIS - Optimized GUI")
    print("="*50)
    print(f"Model: {VOSK_MODEL_PATH}") # Updated print for debugging
    print(f"LLM: {OLLAMA_MODEL}")
    print("="*50)

    root = tk.Tk()
    # Pass the global queues to the App constructor
    app = JarvisApp(root, transcript_queue, reply_queue) 
    root.protocol("WM_DELETE_WINDOW", app._quit)
    root.mainloop()

if __name__ == "__main__":
    main()