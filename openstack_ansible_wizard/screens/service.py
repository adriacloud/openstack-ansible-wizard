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
from textual.containers import ScrollableContainer, Grid, HorizontalGroup
from textual import on
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static, Label

import openstack_ansible_wizard.screens.services as osa_services


class ServicesMainScreen(Screen):
    """A screen for managing OpenStack-Ansible network configurations."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
            self, config_path: str, osa_path: str,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.osa_conf_dir = config_path

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(classes="screen-container"):
            yield Static("OpenStack-Ansible Service Configuration", classes="title")
            with Grid(classes="service-common-column"):
                yield HorizontalGroup(
                    Label("General configuration", classes="service-label"),
                    Button("Manage", id="generic_config", variant="primary", classes="service-button"),
                    classes="service-common-row",
                )
                yield Label()
                yield HorizontalGroup(
                    Label("HAProxy/Keepalived", classes="service-label"),
                    Button("Manage", id="haproxy_config", variant="primary", classes="service-button"),
                    classes="service-common-row",
                )
        yield Footer()

    @on(Button.Pressed, "#haproxy_config")
    def edit_haproxy_configuration(self):
        self.app.push_screen(osa_services.haproxy.HAProxyConfigScreen(config_path=self.osa_conf_dir))

    @on(Button.Pressed, "#generic_config")
    def edit_generic_configuration(self):
        self.app.push_screen(osa_services.generic.GenericConfigScreen(config_path=self.osa_conf_dir))

    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.dismiss(None)
