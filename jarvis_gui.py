# jarvis_gui.py - Animated JARVIS GUI
import tkinter as tk
from tkinter import ttk
import math
import random
import threading
import time

class JarvisGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("JARVIS")
        
        # Make window transparent and frameless
        self.root.attributes('-transparentcolor', 'black')
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)  # Remove title bar
        
        # Window size
        self.width = 300
        self.height = 300
        self.root.geometry(f"{self.width}x{self.height}+100+100")
        
        # Canvas for drawing
        self.canvas = tk.Canvas(
            self.root, 
            width=self.width, 
            height=self.height,
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack()
        
        # Status label
        self.status_label = tk.Label(
            self.root,
            text="JARVIS",
            font=("Arial", 12, "bold"),
            fg="#00D9FF",
            bg="black"
        )
        self.status_label.place(x=self.width//2, y=self.height-30, anchor="center")
        
        # Animation variables
        self.center_x = self.width // 2
        self.center_y = self.height // 2
        self.base_radius = 60
        self.current_radius = self.base_radius
        self.angle = 0
        self.thinking = False
        self.listening = False
        
        # Morph parameters
        self.morph_points = 8
        self.morph_offsets = [0] * self.morph_points
        self.morph_targets = [0] * self.morph_points
        
        # Colors
        self.idle_color = "#00D9FF"  # Cyan
        self.listening_color = "#00FF00"  # Green
        self.thinking_color = "#FF6600"  # Orange
        self.speaking_color = "#0066FF"  # Blue
        
        self.current_color = self.idle_color
        
        # Particle effects
        self.particles = []
        
        # Dragging
        self.drag_data = {"x": 0, "y": 0}
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        
        # Start animation
        self.animate()
        
    def start_drag(self, event):
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
    
    def on_drag(self, event):
        dx = event.x - self.drag_data["x"]
        dy = event.y - self.drag_data["y"]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
    
    def set_status(self, status):
        """Update status text"""
        self.status_label.config(text=status)
    
    def set_idle(self):
        """Idle state"""
        self.thinking = False
        self.listening = False
        self.current_color = self.idle_color
        self.set_status("JARVIS - Idle")
    
    def set_listening(self):
        """Listening state"""
        self.thinking = False
        self.listening = True
        self.current_color = self.listening_color
        self.set_status("Listening...")
    
    def set_thinking(self):
        """Thinking state - makes it jiggle and morph"""
        self.thinking = True
        self.listening = False
        self.current_color = self.thinking_color
        self.set_status("Thinking...")
        # Set random morph targets
        for i in range(self.morph_points):
            self.morph_targets[i] = random.uniform(-15, 15)
    
    def set_speaking(self):
        """Speaking state"""
        self.thinking = False
        self.listening = False
        self.current_color = self.speaking_color
        self.set_status("Speaking...")
    
    def draw_morphing_circle(self):
        """Draw a morphing organic circle"""
        self.canvas.delete("all")
        
        # Update morph offsets smoothly
        for i in range(self.morph_points):
            diff = self.morph_targets[i] - self.morph_offsets[i]
            self.morph_offsets[i] += diff * 0.1
        
        # Calculate points for polygon
        points = []
        for i in range(self.morph_points):
            angle = (i / self.morph_points) * 2 * math.pi
            
            # Add jiggle when thinking
            if self.thinking:
                jiggle = math.sin(self.angle * 3 + i) * 5
            else:
                jiggle = 0
            
            # Add pulse when listening
            if self.listening:
                pulse = math.sin(self.angle * 2) * 10
            else:
                pulse = 0
            
            radius = self.base_radius + self.morph_offsets[i] + jiggle + pulse
            
            x = self.center_x + radius * math.cos(angle)
            y = self.center_y + radius * math.sin(angle)
            points.extend([x, y])
        
        # Draw main shape
        self.canvas.create_polygon(
            points,
            fill=self.current_color,
            outline=self.current_color,
            width=2,
            smooth=True
        )
        
        # Draw glow effect (outer ring)
        glow_points = []
        for i in range(self.morph_points):
            angle = (i / self.morph_points) * 2 * math.pi
            if self.thinking:
                jiggle = math.sin(self.angle * 3 + i) * 5
            else:
                jiggle = 0
            if self.listening:
                pulse = math.sin(self.angle * 2) * 10
            else:
                pulse = 0
            
            radius = self.base_radius + self.morph_offsets[i] + jiggle + pulse + 10
            x = self.center_x + radius * math.cos(angle)
            y = self.center_y + radius * math.sin(angle)
            glow_points.extend([x, y])
        
        self.canvas.create_polygon(
            glow_points,
            fill="",
            outline=self.current_color,
            width=1,
            smooth=True
        )
        
        # Draw center core
        core_size = 8
        if self.thinking:
            core_size += math.sin(self.angle * 5) * 3
        
        self.canvas.create_oval(
            self.center_x - core_size,
            self.center_y - core_size,
            self.center_x + core_size,
            self.center_y + core_size,
            fill="white",
            outline=""
        )
        
        # Draw particles when thinking
        if self.thinking:
            self.update_particles()
    
    def update_particles(self):
        """Create and update particle effects"""
        # Create new particles
        if random.random() > 0.7:
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 3)
            self.particles.append({
                'x': self.center_x,
                'y': self.center_y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': 30
            })
        
        # Update and draw particles
        for particle in self.particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['life'] -= 1
            
            if particle['life'] <= 0:
                self.particles.remove(particle)
            else:
                # Draw particle
                size = particle['life'] / 10
                self.canvas.create_oval(
                    particle['x'] - size,
                    particle['y'] - size,
                    particle['x'] + size,
                    particle['y'] + size,
                    fill=self.current_color,
                    outline=""
                )
    
    def animate(self):
        """Main animation loop"""
        self.angle += 0.1
        
        # Random shape changes when thinking
        if self.thinking and random.random() > 0.95:
            idx = random.randint(0, self.morph_points - 1)
            self.morph_targets[idx] = random.uniform(-15, 15)
        
        # Reset to smooth when idle
        if not self.thinking:
            for i in range(self.morph_points):
                self.morph_targets[i] *= 0.95
        
        self.draw_morphing_circle()
        
        # Continue animation
        self.root.after(33, self.animate)  # ~30 FPS

def demo_states(gui):
    """Demo function to cycle through states"""
    time.sleep(2)
    
    while True:
        # Idle
        gui.set_idle()
        time.sleep(3)
        
        # Listening
        gui.set_listening()
        time.sleep(2)
        
        # Thinking
        gui.set_thinking()
        time.sleep(3)
        
        # Speaking
        gui.set_speaking()
        time.sleep(2)

if __name__ == "__main__":
    root = tk.Tk()
    gui = JarvisGUI(root)
    
    # Start demo in background thread
    demo_thread = threading.Thread(target=demo_states, args=(gui,), daemon=True)
    demo_thread.start()
    
    root.mainloop()