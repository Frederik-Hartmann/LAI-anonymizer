import logging
import string
import tkinter as tk
from typing import Tuple, Union

import customtkinter as ctk

from anonymizer.controller.project import ProjectController
from anonymizer.model.project import XnatConfig
from anonymizer.utils.translate import _
from anonymizer.view.ux_fields import str_entry

logger = logging.getLogger(__name__)


class XnatDialog(tk.Toplevel):
    """
    A dialog window for entering XNAT configuration.

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

    def __init__(
        self,
        parent,
        export_to_xnat: bool,
        xnat_configuration: XnatConfig,
    ):
        super().__init__(master=parent)
        self.xnat_configuration = xnat_configuration
        self.export_to_xnat = export_to_xnat
        self.title(_("XNAT Configuration"))
        self.resizable(False, False)
        self._user_input: Union[Tuple[bool, XnatConfig], None] = None
        self._create_widgets()
        self.wait_visibility()
        self.lift()
        self.grab_set()  # make dialog modal
        self.bind("<Return>", self._enter_keypress)
        self.bind("<Escape>", self._escape_keypress)

    @property
    def user_input(self) -> Union[Tuple[bool, XnatConfig], None]:
        return self._user_input

    def _create_widgets(self):
        logger.info("_create_widgets")
        PAD = 10

        char_width_px = ctk.CTkFont().measure("A")
        logger.info(f"Font Character Width in pixels: ±{char_width_px}")

        self._frame = ctk.CTkFrame(self)
        self._frame.grid(row=0, column=0, padx=PAD, pady=PAD, sticky="nswe")

        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

        row = 0

        self.server_uri_var = str_entry(
            view=self._frame,
            label=_("XNAT Server URI") + ":",
            initial_value=self.xnat_configuration.server_uri,
            min_chars=1,
            max_chars=64,
            charset=string.digits + "-. ^%$@!~+*&" + string.ascii_letters,
            tooltipmsg=None,
            row=row,
            col=0,
            pad=PAD,
            sticky="nw",
        )

        row += 1

        self.project_name_var = str_entry(
            view=self._frame,
            label=_("XNAT Project Name") + ":",
            initial_value=self.xnat_configuration.project_name,
            min_chars=1,
            max_chars=64,
            charset=string.digits + "-_" + string.ascii_lowercase,
            tooltipmsg=None,
            row=row,
            col=0,
            pad=PAD,
            sticky="nw",
        )

        row += 1

        self.username_var = str_entry(
            view=self._frame,
            label=_("Username") + ":",
            initial_value=self.xnat_configuration.username,
            min_chars=3,
            max_chars=64,
            charset=string.digits + "-_." + string.ascii_letters,
            tooltipmsg=None,
            row=row,
            col=0,
            pad=PAD,
            sticky="nw",
        )

        row += 1

        export_to_xnat_label = ctk.CTkLabel(self._frame, text=_("Export to XNAT") + ":")
        export_to_xnat_label.grid(row=row, column=0, padx=PAD, pady=(PAD, 0), sticky="nw")

        self._export_to_xnat_checkbox = ctk.CTkCheckBox(self._frame, text="")
        if self.export_to_xnat:
            self._export_to_xnat_checkbox.select()

        self._export_to_xnat_checkbox.grid(
            row=row,
            column=1,
            padx=PAD,
            pady=PAD,
            sticky="w",
        )

        self._ok_button = ctk.CTkButton(self._frame, width=100, text=_("Ok"), command=self._ok_event)
        self._ok_button.grid(
            row=row,
            column=1,
            padx=PAD,
            pady=PAD,
            sticky="e",
        )

    def _enter_keypress(self, event):
        logger.info("_enter_pressed")
        self._ok_event()

    def _ok_event(self, event=None):
        self._user_input = (
            self._export_to_xnat_checkbox.get() == 1,
            XnatConfig(
                self.server_uri_var.get(),
                self.project_name_var.get(),
                self.username_var.get(),
            ),
        )
        self.grab_release()
        self.destroy()

    def _escape_keypress(self, event):
        logger.info("_escape_pressed")
        self._on_cancel()

    def _on_cancel(self):
        self.grab_release()
        self.destroy()

    def get_input(self):
        self.focus()
        self.master.wait_window(self)
        return self._user_input
    


class XnatCredentialsDialog(tk.Toplevel):
    """
    A dialog window for entering XNAT configuration.

    Args:
        parent: The parent widget.
        project_controller (ProjectController): The project controller.

    Attributes:
        user_input (str | None): The user input containing the password. 

    Methods:
        _create_widgets: Create the widgets for the dialog.
        _enter_keypress: Event handler for the Enter key press.
        _ok_event: Event handler for the Ok button click.
        _escape_keypress: Event handler for the Escape key press.
        _on_cancel: Event handler for canceling the dialog.
        get_input: Get the user input from the dialog.
    """

    def __init__(
        self,
        parent,
        project_controller : ProjectController
    ):
        super().__init__(master=parent)
        self.project_controller = project_controller
        self.title(_("XNAT Log-in"))
        self.resizable(False, False)
        self._user_input: tuple[str | None, str | None] = (self.project_controller.model.xnat_config.username,None)
        self._create_widgets()
        self.wait_visibility()
        self.lift()
        self.grab_set()  # make dialog modal
        self.bind("<Return>", self._enter_keypress)
        self.bind("<Escape>", self._escape_keypress)

    @property
    def user_input(self) -> tuple[str | None, str | None]:
        return self._user_input

    def _create_widgets(self):
        logger.info("_create_widgets")
        PAD = 10

        char_width_px = ctk.CTkFont().measure("A")
        logger.info(f"Font Character Width in pixels: ±{char_width_px}")

        self._frame = ctk.CTkFrame(self)
        self._frame.grid(row=0, column=0, padx=PAD, pady=PAD, sticky="nswe")

        self.columnconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

        row = 0

        self.username_var = str_entry(
            view=self._frame,
            label=_("XNAT Username") + ":",
            initial_value=self.project_controller.model.xnat_config.username,
            min_chars=3,
            max_chars=64,
            charset=string.ascii_letters + string.digits + " !#$%&()#*+-.,:;_^@?~|",
            tooltipmsg=None,
            row=row,
            col=0,
            pad=PAD,
            sticky="nw",
            password=False,
        )

        row +=1

        self.password_var = str_entry(
            view=self._frame,
            label=_("XNAT Password") + ":",
            initial_value=self.project_controller._xnat_password,
            min_chars=6,
            max_chars=64,
            charset=string.ascii_letters + string.digits + " !#$%&()#*+-.,:;_^@?~|",
            tooltipmsg=None,
            row=row,
            col=0,
            pad=PAD,
            sticky="nw",
            password=True,
        )

        self._ok_button = ctk.CTkButton(self._frame, width=100, text=_("Log-in"), command=self._ok_event)
        self._ok_button.grid(
            row=row,
            column=1,
            padx=PAD,
            pady=PAD,
            sticky="e",
        )

    def _enter_keypress(self, event):
        logger.info("_enter_pressed")
        self._ok_event()

    def _ok_event(self, event=None):
        self._user_input = (self.username_var.get(), self.password_var.get())
        self.grab_release()
        self.destroy()

    def _escape_keypress(self, event):
        logger.info("_escape_pressed")
        self._on_cancel()

    def _on_cancel(self):
        self.grab_release()
        self.destroy()

    def get_input(self):
        self.focus()
        self.master.wait_window(self)
        return self._user_input
