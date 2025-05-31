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
from textual.containers import Container
from textual.widgets import Header, Footer, Static
from textual.screen import Screen


class ConfigurationScreen(Screen):
    """A placeholder screen for future configuration options."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the configuration screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield Static("OpenStack-Ansible Configuration", classes="title")
            yield Static("This screen will eventually contain "
                         "configuration options.")
            yield Static("For now, it's a placeholder.")
        yield Footer()

    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.app.pop_screen()
