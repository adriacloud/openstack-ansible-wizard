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

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from textual import on


class ConfirmExitScreen(ModalScreen[bool]):
    """A modal screen to confirm exiting with unsaved changes."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, message: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.message = message

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self.message, classes="title", id="confirm_question"),
            Button("Yes", variant="error", id="confirm_yes"),
            Button("No", variant="primary", id="confirm_no"),
            id="confirm_dialog"
        )

    @on(Button.Pressed, "#confirm_yes")
    def on_exit_button(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#confirm_no")
    def action_pop_screen(self) -> None:
        self.dismiss(False)
