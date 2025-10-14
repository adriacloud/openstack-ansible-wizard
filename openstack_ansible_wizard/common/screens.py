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
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, Static, Input
from textual import on, work

from openstack_ansible_wizard.common import utils
from openstack_ansible_wizard.extensions.button import NavigableButton


class ConfirmExitScreen(ModalScreen[bool]):
    """A modal screen to confirm exiting with unsaved changes."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, message: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        if not message:
            message = "Are you sure you want to exit?"
        self.message = message

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self.message, classes="title", id="confirm_question"),
            NavigableButton("Yes", variant="error", id="confirm_yes"),
            NavigableButton("No", variant="primary", id="confirm_no"),
            id="confirm_dialog"
        )

    @on(Button.Pressed, "#confirm_yes")
    def on_exit_button(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm_no")
    def action_pop_screen(self) -> None:
        self.dismiss(False)


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


class WizardConfigScreen(Screen):
    """A base screen for wizard pages that handles unsaved changes before exiting."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("q", "safe_quit", "Quit"),
        ("s", "save_configs", "Save"),
    ]

    @classmethod
    def get_managed_keys(cls) -> set[str]:
        """Returns a set of configuration keys managed by this screen."""
        return set()

    def has_unsaved_changes(self) -> bool:
        """This method should be implemented by subclasses to report if there are any unsaved changes."""
        return False

    def action_save_configs(self) -> None:
        """This method should be implemented by subclasses to handle saving."""
        pass

    def action_safe_quit(self) -> None:
        """Handle quit binding by safely popping the screen."""
        self.action_pop_screen(action="quit")

    @work
    async def action_pop_screen(self, action: str = "pop") -> None:
        """Pops the screen or exits the app, confirming if there are unsaved changes."""
        if self.has_unsaved_changes():
            message = "You have unsaved changes.\nAre you sure you want to exit?"
            proceed = await self.app.push_screen_wait(ConfirmExitScreen(message=message))
            if not proceed:
                return

        if action == 'pop':
            self.app.pop_screen()
        elif action == 'quit':
            self.app.exit()
