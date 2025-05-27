import logging
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from tkinter import Toplevel, scrolledtext, messagebox, filedialog

from anonymizer.utils.storage import load_pseudo_keys
from anonymizer.model.project import ProjectModel


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
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.on_cancel()
        self.grab_release()
        self.master.lift()
        self.destroy()


class PseudoKeySection:
    def __init__(self, master, frame: ctk.CTkFrame, model: ProjectModel, row_start: int = 0) -> None:
        self.master = master
        self._frame = frame
        self.model = model
        self.row = row_start

        self.pseudo_key_switch_var = ctk.BooleanVar(value=self.model.pseudo_key_config.pseudo_key_lookup_enabled)

        self._build_ui()

    def _build_ui(self) -> None:
        # Switch label
        switch_label = ctk.CTkLabel(self._frame, text="Enable Key Lookup from file:")
        switch_label.grid(row=self.row, column=0, padx=10, pady=(10, 0), sticky="nw")

        # Switch
        self.pseudo_key_switch = ctk.CTkSwitch(
            self._frame,
            text="",
            variable=self.pseudo_key_switch_var,
            onvalue=True,
            offvalue=False,
            command=self._on_switch_toggle,
        )
        self.pseudo_key_switch.grid(row=self.row, column=1, padx=10, pady=(10, 0), sticky="nw")

        # Disable switch if not new model
        if not getattr(self.master, "new_model", False):
            self.pseudo_key_switch.configure(state="disabled")
            self.pseudo_key_switch.configure(fg_color="gray", progress_color="gray")

        self.row += 1

        # File select button (shown conditionally)
        self.file_button_label = ctk.CTkLabel(self._frame, text="Select Anonymization Key File:")
        self.select_button = ctk.CTkButton(
            self._frame,
            text="Select Anonymization Key File",
            command=self._on_select_file,
        )

        if self.pseudo_key_switch_var.get():
            self._show_file_button()

    def _on_switch_toggle(self) -> None:
        enabled = self.pseudo_key_switch_var.get()

        if enabled:
            confirmed = messagebox.askyesno(
                title=("Enable Pseudo Key Lookup?"),
                message=(
                    "Pseudo Key Lookup uses an anonymization key file to map patient IDs.\n\n"
                    "Ensure the selected file is valid and that the 'anonymous patient ID' column contains no PHI.\n\n"
                    "To support this functionality, all incoming datasets—whether received via network or imported from files—will also be stored in the private subdirectory of the storage folder.\n\n"
                    "You should manually delete the key file afterward to maintain irretractable anonymization.\n\n"
                    "Do you want to proceed?"
                ),
            )
            self.master.lift()
            self.master.focus_force()

            if not confirmed:
                self.pseudo_key_switch_var.set(False)
                return

            self.model.pseudo_key_config.pseudo_key_lookup_enabled = True
            self._show_file_button()
        else:
            self.pseudo_key_switch_var.set(False)
            self.model.pseudo_key_config.pseudo_key_lookup_enabled = False
            self.model.pseudo_key_config.pseudo_key_file_path = None
            self._hide_file_button()

    def _show_file_button(self) -> None:
        self.file_button_label.grid(row=self.row, column=0, padx=10, pady=(10, 0), sticky="nw")
        self.select_button.grid(row=self.row, column=1, columnspan=2, padx=10, pady=(10, 0), sticky="nw")

    def _hide_file_button(self) -> None:
        self.select_button.grid_forget()
        self.file_button_label.grid_forget()

    def _on_select_file(self) -> None:
        file_path_str = filedialog.askopenfilename(
            title="Select Anonymization Key File",
            filetypes=[("CSV or Excel Files", "*.csv *.xlsx"), ("All Files", "*.*")]
        )

        if not file_path_str:
            return  # no file selected, do nothing

        self._pending_file_path = Path(file_path_str)

        PseudoKeyConfirmationDialog(
            master=self.master,
            file_path=self._pending_file_path,
            on_confirm=self._on_confirm,
            on_cancel=self._on_cancel,
        )

    def _on_confirm(self, _: Path) -> None:
        self.model.pseudo_key_config.pseudo_key_lookup_enabled = True
        self.model.pseudo_key_config.pseudo_key_file_path = self._pending_file_path
        self.pseudo_key_switch_var.set(True)

    def _on_cancel(self) -> None:
        pass

