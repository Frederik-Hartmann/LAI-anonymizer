import logging
from pathlib import Path
from typing import Callable
import tkinter as tk

import customtkinter as ctk
from tkinter import scrolledtext, messagebox, filedialog

from anonymizer.utils.storage import load_pseudo_keys
from anonymizer.utils.translate import _
from anonymizer.model.project import ProjectModel, PseudoKeyConfig


logger = logging.getLogger(__name__)


class PseudoKeyDialog(tk.Toplevel):
    """
    A dialog window for entering Pseudo Key Lookup configuration.

    Args:
        parent: The parent widget.
        export_to_xnat (bool): Flag indicating whether to export to XNAT.
        xnat_configuration (XnatConfig): An instance of the XnatConfig class.

    Attributes:
        user_input (Union[Tuple[bool, XnatConfig], None]): The user input containing the export flag and XnatConfig instance.

    Methods:
        _create_widgets: Create the widgets for the dialog.
        _enter_keypress: Event handler for the Enter key press.
        _ok_event: Event handler for the Ok button click.
        _escape_keypress: Event handler for the Escape key press.
        _on_cancel: Event handler for canceling the dialog.
        get_input: Get the user input from the dialog.
    """

    def __init__(self, parent, initial_config: PseudoKeyConfig):
        super().__init__(master=parent)
        self._initial_config = initial_config
        self._user_input: PseudoKeyConfig | None = None
        self._enable_lookup_var = ctk.BooleanVar(value=initial_config.pseudo_key_lookup_enabled)
        self._selected_key_file_path: Path | None = initial_config.pseudo_key_file_path

        self.title(_("Pseudo Key Lookup Configuration"))
        self.resizable(False, False)
        self._create_widgets()
        self._setup_bindings()
        self.wait_visibility()
        self.lift()
        self.grab_set()

    @property
    def user_input(self) -> PseudoKeyConfig | None:
        """Return the users input configuration."""
        return self._user_input

    def _create_widgets(self) -> None:
        PAD = 10
        self._frame = ctk.CTkFrame(self)
        self._frame.grid(row=0, column=0, padx=PAD, pady=PAD, sticky="nswe")

        row = 0

        # File selection
        file_label = ctk.CTkLabel(self._frame, text=_("Select Anonymization Key File:"))
        file_label.grid(row=row, column=0, padx=PAD, pady=PAD, sticky="w")

        self.file_btn = ctk.CTkButton(
            self._frame,
            text=(self._initial_config.pseudo_key_file_path if self._initial_config.pseudo_key_file_path else _("Select Anonymization Key File")),
            command=self._on_select_file
        )
        self.file_btn.grid(row=row, column=1, padx=PAD, pady=PAD, sticky="w")

        row += 1
        # Quarantine selection
        self.quarantine_switch_var = tk.BooleanVar(value=self._initial_config.quarantine_on_lookup_error)
        self.quarantine_label = ctk.CTkLabel(
            self._frame,
            text=_("On missing ID:"),
        )
        self.quarantine_label.grid(row=row, column=0, padx=PAD, pady=(PAD, 0), sticky="w")

        quarantine_switch_frame = ctk.CTkFrame(self._frame, fg_color="transparent")
        quarantine_switch_frame.grid(row=row, column=1, padx=PAD, pady=(PAD, 0), sticky="w")

        self.quarantine_left_label = ctk.CTkLabel(
            quarantine_switch_frame,
            text=_("Auto-generate ID"),
            font=ctk.CTkFont(weight="normal" if self.quarantine_switch_var.get() else "bold")
        )
        self.quarantine_left_label.pack(side="left", padx=(0, 0))

        self.quarantine_switch = ctk.CTkSwitch(
            quarantine_switch_frame,
            text="",
            variable=self.quarantine_switch_var,
            onvalue=True,
            offvalue=False,
            command=self._on_quarantine_switch_toggle,
        )
        self.quarantine_switch.pack(side="left", padx=5)

        self.quarantine_right_label = ctk.CTkLabel(
            quarantine_switch_frame,
            text=_("Quarantine"),
            font=ctk.CTkFont(weight="bold" if self.quarantine_switch_var.get() else "normal")
        )
        self.quarantine_right_label.pack(side="left", padx=(5, 0))

        row += 1

        # Lookup switch
        switch_label = ctk.CTkLabel(self._frame, text=_("Enable Key Lookup from file:"))
        switch_label.grid(row=row, column=0, padx=PAD, pady=(PAD, 0), sticky="nw")

        self._lookup_switch = ctk.CTkSwitch(
            self._frame,
            text="",
            variable=self._enable_lookup_var,
            onvalue=True,
            offvalue=False,
            command=self._on_toggle_switch
        )
        self._lookup_switch.grid(row=row, column=1, padx=PAD, pady=(PAD, 0), sticky="nw")

        if not getattr(self.master, "new_model", False):
            self._lookup_switch.configure(state="disabled", fg_color="gray", progress_color="gray")

        row += 1
        

        ok_btn = ctk.CTkButton(self._frame, width=100, text=_("Ok"), command=self._on_ok)
        ok_btn.grid(row=row, column=1, padx=PAD, pady=PAD, sticky="e")

    def _setup_bindings(self) -> None:
        self.bind("<Return>", self._on_ok)
        self.bind("<Escape>", self._on_cancel)

    def _on_toggle_switch(self) -> None:
        if self._enable_lookup_var.get() and not self._selected_key_file_path:
            if not self._show_confirmation_dialog():
                self._enable_lookup_var.set(False)

    def _on_select_file(self) -> None:
        top = tk.Toplevel(self)
        top.withdraw()
        top.lift()
        top.attributes("-topmost", True)
        top.focus_force()

        file_path_str = filedialog.askopenfilename(
            title=_("Select Anonymization Key File"),
            filetypes=[("CSV or Excel Files", "*.csv *.xlsx"), ("All Files", "*.*")],
            parent=top,
        )

        top.grab_release()
        top.destroy()
        self.lift()
        self.focus()

        if not file_path_str:
            return

        file_path = Path(file_path_str)
        dialog = PseudoKeyConfirmationDialog(master=self.master, file_path=file_path)
        if dialog.get_input():
            self._selected_key_file_path = file_path
        self.file_btn.configure(text=file_path.name)

    def _on_quarantine_switch_toggle(self) -> None:
        """Update label font styles based on switch selection."""
        is_quarantine = self.quarantine_switch_var.get()
        bold_font = ctk.CTkFont(weight="bold")
        normal_font = ctk.CTkFont(weight="normal")

        self.quarantine_left_label.configure(font=normal_font if is_quarantine else bold_font)
        self.quarantine_right_label.configure(font=bold_font if is_quarantine else normal_font)

        
    def _on_ok(self, event=None) -> None:
        self._user_input = PseudoKeyConfig(
            pseudo_key_lookup_enabled=self._enable_lookup_var.get(),
            quarantine_on_lookup_error=self.quarantine_switch_var.get(),
            pseudo_key_file_path=self._selected_key_file_path
        )
        self.grab_release()
        self.destroy()

    def _on_cancel(self, event=None) -> None:
        self.grab_release()
        self.destroy()

    def get_input(self) -> PseudoKeyConfig | None:
        """Wait for window close and return the resulting configuration."""
        self.focus()
        self.master.wait_window(self)
        return self._user_input

    def _show_confirmation_dialog(self) -> bool:
        top = tk.Toplevel(self)
        top.withdraw()
        top.lift()
        top.attributes("-topmost", True)
        top.focus_force()

        confirmed = messagebox.askyesno(
            title=_("Enable Pseudo Key Lookup?"),
            message=_(
                "Pseudo Key Lookup uses an anonymization key file to map patient IDs.\n\n"
                "Ensure the selected file is valid and that the 'anonymous patient ID' column contains no PHI.\n\n"
                "To support this functionality, all incoming datasets—whether received via network or imported "
                "from files—will also be stored in the private subdirectory of the storage folder.\n\n"
                "You should manually delete the key file afterward to maintain irretractable anonymization.\n\n"
                "Do you want to proceed?"
            ),
            parent=top
        )

        top.grab_release()
        top.destroy()
        self.lift()
        self.focus()
        return confirmed

class PseudoKeyConfirmationDialog(tk.Toplevel):
    """
    A modal dialog to review and confirm anonymization key mappings.

    Args:
        master: The parent Tk widget.
        file_path (Path): Path to the anonymization key file.

    Attributes:
        file_path (Path): File selected for pseudo key lookup.
        mapping (dict): Parsed anonymization key mappings.
        messages (list[str]): Parsing warnings or info.
        _confirmed (bool): Whether the user confirmed.
    """

    def __init__(self, master, file_path: Path):
        super().__init__(master)
        self.file_path = file_path
        self.mapping: dict = {}
        self.messages: list[str] = []
        self._confirmed = False

        self.title("Confirm Anonymization Key Mapping")
        self.geometry("800x500")
        self.resizable(False, False)
        self.grab_set()

        self._create_widgets()

    def _create_widgets(self) -> None:
        """Build and layout the confirmation dialog widgets."""
        label = ctk.CTkLabel(self, text="Review the mapping of ORIGINAL → ANONYMIZED IDs:")
        label.pack(pady=(10, 2), padx=10)

        try:
            self.mapping, self.messages = load_pseudo_keys(self.file_path)
        except Exception as e:
            self._show_error("Error", f"An unexpected error occurred: {e}")
            self._cancel_event()
            return

        if not self.mapping:
            msg = "\n".join(self.messages) if self.messages else "No valid mappings found."
            self._show_warning("Warning", msg)
            self._cancel_event()
            return

        self._create_mapping_textbox()

        if self.messages:
            self._create_warning_box()

        self._create_button_frame()

    def _create_mapping_textbox(self) -> None:
        """Show key mappings in a read-only scrolled text widget."""
        text = scrolledtext.ScrolledText(self, height=15, wrap="word")
        text.insert("end", f"{'ORIGINAL':<60} → ANONYMIZED\n")
        text.insert("end", "-" * 80 + "\n")
        for orig, anon in self.mapping.items():
            text.insert("end", f"{orig:<60} → {anon}\n")
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=10, pady=5)

    def _create_warning_box(self) -> None:
        """Display warnings related to the key file."""
        box = scrolledtext.ScrolledText(self, height=6, wrap="word", fg="red")
        box.insert("end", "Warnings:\n")
        box.insert("end", "\n".join(self.messages))
        box.configure(state="disabled")
        box.pack(fill="x", padx=10, pady=(5, 10))

    def _create_button_frame(self) -> None:
        """Add confirm and cancel buttons."""
        frame = ctk.CTkFrame(self)
        frame.pack(pady=10)

        confirm_btn = ctk.CTkButton(frame, text="Confirm", command=self._confirm_event)
        cancel_btn = ctk.CTkButton(frame, text="Cancel", command=self._cancel_event)

        confirm_btn.grid(row=0, column=0, padx=5)
        cancel_btn.grid(row=0, column=1, padx=5)

    def _confirm_event(self) -> None:
        """Handle user confirmation."""
        self._confirmed = True
        self.grab_release()
        self.destroy()

    def _cancel_event(self) -> None:
        """Handle user cancellation."""
        self._confirmed = False
        self.grab_release()
        self.destroy()

    def _show_error(self, title: str, message: str) -> None:
        """Show an error message dialog."""
        self._show_messagebox(messagebox.showerror, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        """Show a warning message dialog."""
        self._show_messagebox(messagebox.showwarning, title, message)

    def _show_messagebox(self, func, title: str, message: str) -> None:
        """Show a messagebox using a temporary top-level dialog."""
        top = tk.Toplevel(self)
        top.withdraw()
        top.lift()
        top.attributes("-topmost", True)
        top.focus_force()
        func(title=title, message=message, parent=top)
        top.destroy()
        self.lift()
        self.focus()

    def get_input(self) -> bool:
        """
        Wait for the dialog to close and return the user decision.

        Returns:
            bool: True if user confirmed, False otherwise.
        """
        self.focus()
        self.master.wait_window(self)
        return self._confirmed
