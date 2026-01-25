import tkinter as tk

# --- Design System Constants (Seraphic Focus) ---
COLORS = {
    "bg": "#F9F8F4",          # Warm Cream
    "surface": "#FFFFFF",      # White Cards
    "text_primary": "#1C1C1E", # Sharp Black
    "text_secondary": "#8E8E93", # System Gray
    "accent": "#2C3E50",       # Dark Blue/Grey
    "button_bg": "#1C1C1E",    # Black for primary actions
    "button_bg_hover": "#333333", # Dark grey for hover
    "button_text": "#FFFFFF",
    "border": "#E5E5EA",
    "shadow_light": "#E5E5EA", 
    "shadow_lighter": "#F2F2F7",
    "success": "#34C759",      # Subtle green
    "input_bg": "#F2F0EB",     # Light beige for inputs
    "link": "#2C3E50",          # Link color
    "status_gadget": "#EF4444", # Red for errors
    "button_start": "#34C759",  # Green for success/start
    "button_start_hover": "#2DB84C"
}

FONTS = {
    "display": ("Georgia", 32, "bold"),
    "heading": ("Georgia", 24, "bold"),
    "subheading": ("Georgia", 18),
    "body": ("Helvetica", 14),
    "body_bold": ("Helvetica", 14, "bold"),
    "caption": ("Helvetica", 12, "bold"),
    "small": ("Helvetica", 12),
    "input": ("Helvetica", 14)
}

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=200, height=50, radius=25, bg_color=COLORS["button_bg"], hover_color=None, text_color=COLORS["button_text"], font_type="body_bold"):
        super().__init__(parent, width=width, height=height, bg=COLORS["bg"], highlightthickness=0)
        self.command = command
        self.radius = radius
        self.bg_color = bg_color
        self.hover_color = hover_color or bg_color
        self.text_color = text_color
        self.text_str = text
        self.font_type = font_type
        self._original_bg = bg_color
        
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        
        self.draw()

    def draw(self, offset=0):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        
        # Try to use actual size if available
        if self.winfo_width() > 1: w = self.winfo_width()
        if self.winfo_height() > 1: h = self.winfo_height()

        x1, y1 = 2, 2 + offset
        x2, y2 = w - 2, h - 2 + offset
        r = self.radius
        
        if r > h/2: r = h/2
        
        # Shadow
        if offset == 0:
            self.create_rounded_rect(x1+2, y1+4, x2+2, y2+4, r, fill=COLORS["shadow_light"], outline="")

        # Body
        self.create_rounded_rect(x1, y1, x2, y2, r, fill=self.bg_color, outline=self.bg_color)
        
        # Text
        self.create_text(w//2, h//2 + offset, text=self.text_str, fill=self.text_color, font=FONTS[self.font_type])

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text_str = kwargs.pop("text")
        if "bg_color" in kwargs:
            self.bg_color = kwargs.pop("bg_color")
            self._original_bg = self.bg_color
        if "hover_color" in kwargs:
            self.hover_color = kwargs.pop("hover_color")
        if "text_color" in kwargs:
            self.text_color = kwargs.pop("text_color")
            
        super().configure(**kwargs)
        self.draw()

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_click(self, event):
        if self.command:
            self.command()
        self.draw(offset=2)
        self.after(100, lambda: self.draw(offset=0))

    def _on_enter(self, event):
        self.bg_color = self.hover_color
        self.draw()

    def _on_leave(self, event):
        self.bg_color = self._original_bg
        self.draw()

class Card(tk.Canvas):
    def __init__(self, parent, width=300, height=150, radius=20, bg_color=COLORS["surface"]):
        super().__init__(parent, width=width, height=height, bg=COLORS["bg"], highlightthickness=0)
        self.radius = radius
        self.bg_color = bg_color
        self.draw()

    def draw(self):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        r = self.radius
        
        # Soft Shadow
        self.create_rounded_rect(4, 8, w-4, h-4, r, fill=COLORS["shadow_lighter"], outline="")
        
        # Card Body
        self.create_rounded_rect(2, 2, w-6, h-6, r, fill=self.bg_color, outline=COLORS["shadow_lighter"])

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

class StyledEntry(tk.Frame):
    def __init__(self, parent, placeholder="", width=200):
        super().__init__(parent, bg=COLORS["surface"])
        self.placeholder = placeholder
        
        # Container for visual styling
        self.container = tk.Frame(self, bg=COLORS["input_bg"], padx=15, pady=10)
        self.container.pack(fill="x")
        
        # Entry widget
        self.entry = tk.Entry(self.container, font=FONTS["input"], bg=COLORS["input_bg"], 
                            fg=COLORS["text_primary"], relief="flat", highlightthickness=0,
                            insertbackground=COLORS["text_primary"])  # Black cursor
        self.entry.pack(fill="x")
        self.entry.insert(0, placeholder)
        self.entry.config(fg=COLORS["text_secondary"])
        
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Key>", self._on_key_press)
        
        # Bottom border (animated later maybe)
        self.border = tk.Frame(self, bg=COLORS["border"], height=2)
        self.border.pack(fill="x")
        
        # Error label - always packed to reserve space, empty text when no error
        self.error_label = tk.Label(self, text=" ", font=("Helvetica", 11), fg=COLORS["status_gadget"], 
                                   bg=COLORS["surface"], anchor="w", wraplength=300, justify="left", height=1)
        self.error_label.pack(fill="x", pady=(2, 0))
        
        self.command = None
        self._has_feedback = False

    def show_error(self, message):
        self.error_label.config(text=message, fg=COLORS["status_gadget"])
        self.border.config(bg=COLORS["status_gadget"])
        self._has_feedback = True

    def show_success(self, message):
        self.error_label.config(text=message, fg=COLORS["button_start"])
        self.border.config(bg=COLORS["button_start"])
        self._has_feedback = True
        
    def show_info(self, message):
        self.error_label.config(text=message, fg=COLORS["text_secondary"])
        self.border.config(bg=COLORS["accent"])
        self._has_feedback = True

    def clear_error(self):
        self.error_label.config(text=" ")  # Keep space reserved
        self.border.config(bg=COLORS["accent"] if self.entry.focus_get() == self.entry else COLORS["border"])
        self._has_feedback = False

    def _on_focus_in(self, event):
        # Don't clear error on focus in, wait for typing
        if self.entry.get() == self.placeholder:
            self.entry.delete(0, "end")
            self.entry.config(fg=COLORS["text_primary"])
        self.border.config(bg=COLORS["accent"])
        
    def _on_key_press(self, event):
        self.clear_error()

    def _on_focus_out(self, event):
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=COLORS["text_secondary"])
        # Only reset border if no feedback is showing
        if not self._has_feedback:
            self.border.config(bg=COLORS["border"])
        
    def _on_return(self, event):
        if self.command:
            self.command()

    def get(self):
        val = self.entry.get()
        return "" if val == self.placeholder else val
        
    def bind_return(self, command):
        self.command = command
        
    def delete(self, first, last=None):
        self.entry.delete(first, last)
        
    def insert(self, index, string):
        self.entry.insert(index, string)
