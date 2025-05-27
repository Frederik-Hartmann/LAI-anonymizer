from tkinter import Toplevel, scrolledtext, messagebox
import customtkinter as ctk
from pathlib import Path
from typing import Callable
from anonymizer.utils.storage import load_pseudo_keys
import logging

logger = logging.getLogger(__name__)


class PseudoKeyConfirmationDialog(Toplevel):
    def __init__(self, master, file_path: Path, on_confirm: Callable[[Path], None], on_cancel: Callable[[], None]):
        super().__init__(master)
        self.file_path = file_path
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        self.mapping = {}
        self.messages = []

        self._build_ui()

    def _build_ui(self):
        self.title("Confirm Anonymization Key Mapping")
        self.geometry("800x500")
        self.grab_set()

        label = ctk.CTkLabel(self, text="Review the mapping of ORIGINAL → ANONYMIZED IDs:")
        label.pack(pady=(10, 2), padx=10)

        try:
            self.mapping, self.messages = load_pseudo_keys(self.file_path)
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=self)
            self.destroy()
            return

        if not self.mapping:
            full_msg = "\n".join(self.messages) if self.messages else "No valid mappings found."
            messagebox.showwarning("Warning", full_msg, parent=self)
            self.destroy()
            return

        self.text_widget = scrolledtext.ScrolledText(self, height=15, wrap="word")
        self.text_widget.insert("end", f"{'ORIGINAL':<60} → ANONYMIZED\n")
        self.text_widget.insert("end", "-" * 80 + "\n")
        for orig, anon in self.mapping.items():
            self.text_widget.insert("end", f"{orig:<60} → {anon}\n")
        self.text_widget.configure(state="disabled")
        self.text_widget.pack(fill="both", expand=True, padx=10, pady=5)

        if self.messages:
            error_box = scrolledtext.ScrolledText(self, height=6, wrap="word", fg="red")
            error_box.insert("end", "Warnings:\n")
            error_box.insert("end", "\n".join(self.messages))
            error_box.configure(state="disabled")
            error_box.pack(fill="x", padx=10, pady=(5, 10))

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=10)

        confirm_btn = ctk.CTkButton(button_frame, text="Confirm", command=self._confirm)
        cancel_btn = ctk.CTkButton(button_frame, text="Cancel", command=self._cancel)

        confirm_btn.grid(row=0, column=0, padx=5)
        cancel_btn.grid(row=0, column=1, padx=5)

    def _confirm(self):
        self.on_confirm(self.file_path)
        self.destroy()

    def _cancel(self):
        self.on_cancel()
        self.destroy()

