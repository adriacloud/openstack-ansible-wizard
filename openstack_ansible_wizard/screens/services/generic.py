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

import copy

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Grid, HorizontalGroup
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from openstack_ansible_wizard.common.config import load_service_config, save_service_config
from openstack_ansible_wizard.common.screens import ConfirmExitScreen


class GenericConfigScreen(Screen):
    """A modal screen for generic configuration flags."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("s", "save_configs", "Save"),
        ("q", "safe_quit", "Quit"),
    ]

    config_data = reactive(dict)

    def __init__(self, config_path: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.config_path = config_path
        self.initial_data = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="screen-container"):
            yield Static("Generic Configuration", classes="title")
            yield Static(id="generic_status_message", classes="status_message")

            with Grid(classes="service-column"):
                yield HorizontalGroup(
                    Label("Internal Endpoint:", classes="service-label"),
                    Input(id="internal_lb_vip_address", placeholder="e.g., internal.example.cloud"),
                    classes="service-row",
                )

                yield HorizontalGroup(
                    Label("External Endpoint:", classes="service-label"),
                    Input(id="external_lb_vip_address", placeholder="e.g., example.cloud"),
                    classes="service-row",
                )
            yield Button("Save Changes", id="save_button", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#generic_status_message", Static).update("Loading configuration...")
        self.load_configs()

    @work(thread=True)
    def load_configs(self) -> None:
        status_widget = self.query_one("#generic_status_message")
        if status_widget.render().plain != "Loading configuration...":
            status_widget.update("Loading configuration...")

        data, error = load_service_config(self.config_path, "all")
        if error:
            self.query_one("#generic_status_message").update(f"[red]{error}[/red]")
            return

        self.initial_data = copy.deepcopy(data)
        self.config_data = data
        self.call_after_refresh(self.update_widgets)

    def update_widgets(self) -> None:
        """Populate widgets with loaded data."""
        status_widget = self.query_one("#generic_status_message")
        if status_widget.render().plain == "Loading configuration...":
            status_widget.update("")
        self.query_one("#internal_lb_vip_address", Input).value = self.config_data.get("internal_lb_vip_address", "")
        self.query_one("#external_lb_vip_address", Input).value = self.config_data.get("external_lb_vip_address", "")

    @work(thread=True)
    @on(Button.Pressed, "#save_button")
    def action_save_configs(self) -> None:
        """Saves all changes back to the user config file."""
        status_widget = self.query_one("#generic_status_message", Static)
        status_widget.update("Saving...")

        new_config = {
            "internal_lb_vip_address": self.query_one("#internal_lb_vip_address", Input).value,
            "external_lb_vip_address": self.query_one("#external_lb_vip_address", Input).value,
        }

        try:
            save_service_config(self.config_path, "all", new_config)
            status_widget.update("[green]Changes saved successfully.[/green]")
            self.load_configs()
        except Exception as e:
            status_widget.update(f"[red]Error saving file: {e}[/red]")

    def _get_current_config(self) -> dict:
        """Gathers current configuration from widgets."""
        current_config = {
            "internal_lb_vip_address": self.query_one("#internal_lb_vip_address", Input).value,
            "external_lb_vip_address": self.query_one("#external_lb_vip_address", Input).value,
        }
        return current_config

    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        if not self.initial_data:
            return False

        current_config = self._get_current_config()
        initial_config = copy.deepcopy(self.initial_data)

        for key in current_config:
            if current_config.get(key) != initial_config.get(key, ""):
                return True
        return False

    def action_safe_quit(self) -> None:
        """Handle quit binding."""
        self.action_pop_screen(action="quit")

    @work
    async def action_pop_screen(self, action: str = "pop") -> None:
        """Pops the current screen from the screen stack."""

        if self.has_unsaved_changes():
            message = "You have unsaved changes.\nAre you sure you want to exit?"
            proceed = await self.app.push_screen_wait(ConfirmExitScreen(message=message))
            if not proceed:
                return

        if action == 'pop':
            self.app.pop_screen()
        elif action == 'quit':
            self.app.exit()
