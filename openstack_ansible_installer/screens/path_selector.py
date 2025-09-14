# Copyright 2025, Adria Cloud Services.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Grid
from textual import on
from textual.widgets import Button, Static, Input
from textual.screen import ModalScreen

from openstack_ansible_installer.common import utils


class PathInputScreen(ModalScreen):
    """A screen for the user to input a custom path."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self,
                 path_type: str,
                 reversed_checks: bool = False,
                 name: str | None = None,
                 id: str | None = None,
                 classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.path_type = path_type
        self.reversed = reversed_checks

    def compose(self) -> ComposeResult:
        """Create child widgets for the path input screen."""
        yield Grid(
            Static(f"Enter Custom Path for {self.path_type}", classes="title", id="path_input_title"),
            Input(placeholder=f"e.g., /path/to/{self.path_type}", id="path_input"),
            Button("Submit Path", id="submit_path", variant="primary"),
            Static("", id="path_input_message"),
            id="select_path_dialog"
        )

    @on(Input.Submitted, "#path_input")
    @on(Button.Pressed, "#submit_path")
    def submit_path(self) -> None:
        """Processes the submitted path."""
        path_input = self.query_one("#path_input", Input).value
        message_widget = self.query_one("#path_input_message", Static)
        if path_input:
            p = Path(path_input)
            if p.is_dir():
                if self.reversed:
                    message_widget.update(f"[red]Error:[/red] Path '{path_input}' already exist and is a directory.")
                else:
                    message_widget.update(f"[green]Path '{path_input}' is a valid directory.[/green]")
                    self.dismiss(path_input)
            elif p.exists() and self.reversed:
                message_widget.update(f"[red]Error:[/red] Path '{path_input}' already exist")
            else:
                if self.reversed:
                    if utils.path_writable(path_input, parent=True):
                        message_widget.update(f"[green]Path '{path_input}' does not exist and can be used.[/green]")
                        self.dismiss(path_input)
                    else:
                        message_widget.update(
                            "[red]Error:[/red]"
                            f"Unable to use '{path_input}' due to insufficient permissions to parent path.")
                else:
                    message_widget.update(
                        f"[red]Error:[/red] Path '{path_input}' does not exist or is not a directory.")
        else:
            message_widget.update("[red]Error:[/red] Please enter a path.")

    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.dismiss(None)
