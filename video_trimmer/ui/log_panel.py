import datetime
import queue

import customtkinter as ctk


class LogPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._queue: queue.Queue[str] = queue.Queue()

        ctk.CTkLabel(self, text="LOG", font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 4)
        )

        self._textbox = ctk.CTkTextbox(
            self,
            height=160,
            font=ctk.CTkFont(family="monospace", size=11),
            state="disabled",
            wrap="word",
        )
        self._textbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._drain()

    def append(self, message: str):
        """Thread-safe: enqueue a log line."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._queue.put(f"[{ts}] {message}\n")

    def clear(self):
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")

    def _drain(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                self._textbox.configure(state="normal")
                self._textbox.insert("end", msg)
                self._textbox.see("end")
                self._textbox.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain)
