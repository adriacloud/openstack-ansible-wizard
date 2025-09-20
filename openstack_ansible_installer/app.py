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


from textual.app import App

from openstack_ansible_installer.screens.initial import InitialCheckScreen


class OpenStackAnsibleApp(App):
    """The main Textual application for OpenStack-Ansible deployment."""

    CSS_PATH = "css/openstack_ansible_ui.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "toggle_theme", "dark/light")
    ]

    def action_toggle_theme(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark"
            if self.theme == "textual-light"
            else "textual-light"
        )

    def action_quit(self) -> None:
        """Quits the application."""
        self.app.exit()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.push_screen(InitialCheckScreen())

def main():
    app = OpenStackAnsibleApp()
    app.run()
