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
import os
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, HorizontalGroup
from textual.widgets import Header, Footer, Button, Static
from textual.reactive import reactive
from textual.screen import Screen

from screens.configuration import ConfigurationScreen
from screens.editor import FileBrowserEditorScreen
from screens.path_selector import PathInputScreen


class InitialCheckScreen(Screen):
    """The initial screen that checks for OpenStack-Ansible presence."""

    # BINDINGS = [
    #     ("q", "quit", "Quit"),
    # ]

    osa_clone_dir = reactive(os.environ.get('OSA_CLONE_DIR', '/opt/openstack-ansible'))
    osa_conf_dir = os.environ.get('OSA_CONFIG_DIR', '/etc/openstack_deploy')

    def compose(self) -> ComposeResult:
        """Create child widgets for the initial check screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield Static("OpenStack-Ansible Deployment UI", classes="title")
            yield Static("Checking for existing setup...", id="status_message")
            yield Static("", id="osa_path_status")
            yield Static("", id="etc_path_status")
            with HorizontalGroup(classes="button-row"):
                yield Button("Bootstrap OpenStack-Ansible", id="clone_osa", variant="primary", disabled=True)
                yield Button("Custom OpenStack-Ansible Path", id="custom_osa_path", variant="default", disabled=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Generate configuration", id="generate_config", variant="primary", disabled=True)
                yield Button("Custom Configuation Path", id="custom_config_path", variant="default", disabled=True)
                yield Button.warning("Editor", id="open_editor", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.check_paths()

    def on_screen_resume(self) -> None:
        """Called when this screen becomes the active screen again."""
        self.check_paths()

    def check_paths(self) -> None:
        """Performs the path checks and updates the UI."""
        osa_path = Path(self.osa_clone_dir)
        etc_path = Path(self.osa_conf_dir)

        osa_status_widget = self.query_one("#osa_path_status", Static)
        etc_status_widget = self.query_one("#etc_path_status", Static)
        status_message_widget = self.query_one("#status_message", Static)

        clone_button = self.query_one("#clone_osa", Button)
        custom_osa_path_button = self.query_one("#custom_osa_path", Button)
        proceed_config_button = self.query_one("#generate_config", Button)
        custom_config_button = self.query_one("#custom_config_path", Button)
        open_editor_button = self.query_one("#open_editor", Button)

        check_osa_success = False
        check_config_success = False

        if osa_path.is_dir():
            if Path(f'{self.osa_clone_dir}/osa_toolkit/generate.py').is_file():
                osa_status_widget.update(f"[green]✓[/green] {self.osa_clone_dir} exists.")
                clone_button.disabled = True
                custom_osa_path_button.disabled = False
                check_osa_success = True
            else:
                osa_status_widget.update(f"[red]✗[/red] {self.osa_clone_dir} exists, but not "
                                         "proper OpenStack-Ansible folder.")
                clone_button.disabled = False
                custom_osa_path_button.disabled = False
        else:
            osa_status_widget.update(f"[red]✗[/red] {self.osa_clone_dir} does not exist.")
            status_message_widget.update("Please provide the OpenStack-Ansible repository path.")
            clone_button.disabled = False
            custom_osa_path_button.disabled = False

        if etc_path.is_dir():
            self.add_class("config-found")
            if Path(f'{self.osa_conf_dir}/openstack_user_config.yml').is_file():
                etc_status_widget.update(f"[green]✓[/green] {self.osa_conf_dir} exists.")
                status_message_widget.update(f"Directory {self.osa_conf_dir} found. Opening editor...")
                proceed_config_button.disabled = True
                open_editor_button.disabled = False
                check_config_success = True
            else:
                etc_status_widget.update(f"[red]✗[/red] {self.osa_conf_dir} exists but is not yet configured.")
                proceed_config_button.disabled = False
                open_editor_button.disabled = False
                custom_config_button.disabled = False
        else:
            self.add_class("no-config")
            etc_status_widget.update(f"[red]✗[/red] {self.osa_conf_dir} does not exist.")
            if osa_path.is_dir():  # Only suggest config if OSA repo is found
                status_message_widget.update(f"No {self.osa_conf_dir} found. Proceed to configuration.")
                proceed_config_button.disabled = False
                custom_config_button.disabled = False
            open_editor_button.disabled = True

        if check_osa_success and check_config_success:
            # Automatically switch to editor if all required settings exist
            self.call_after_refresh(lambda: self.app.push_screen(FileBrowserEditorScreen(initial_path=str(etc_path))))

    @on(Button.Pressed, "#clone_osa")
    def clone_repo(self) -> None:
        """Simulates cloning the OpenStack-Ansible repository."""
        self.query_one("#status_message", Static).update("Attempting to clone OpenStack-Ansible...")
        # In a real application, you would use subprocess.run() here
        # For demonstration, we'll just show a message.
        try:
            # Example: subprocess.run(
            #   ["git", "clone", "https://github.com/openstack/openstack-ansible.git", "/opt/openstack-ansible"],
            #   check=True)
            self.log("Simulating git clone...")
            self.query_one("#status_message", Static).update(
                "[green]Simulated cloning complete.[/green] Please restart the app to re-check.")
            self.query_one("#clone_osa", Button).disabled = True
            self.query_one("#custom_osa_path", Button).disabled = True
        except Exception as e:
            self.query_one("#status_message", Static).update(f"[red]Error during clone:[/red] {e}")

    @on(Button.Pressed, "#custom_osa_path")
    @work
    async def enter_custom_osa_path(self) -> None:
        """Pushes the screen to enter a custom path and awaits the result."""
        custom_osa_path_resp = await self.app.push_screen_wait(PathInputScreen(path_type="openstack-ansible"))
        if custom_osa_path_resp:
            self.osa_clone_dir = custom_osa_path_resp  # Update the reactive path
            self.check_paths()  # Re-check paths with the new custom path

    @on(Button.Pressed, "#custom_config_path")
    @work
    async def enter_custom_config_path(self) -> None:
        """Pushes the screen to enter a custom path and awaits the result."""
        custom_osa_config_resp = await self.app.push_screen_wait(PathInputScreen(path_type="openstack_deploy"))
        if custom_osa_config_resp:
            self.osa_conf_dir = custom_osa_config_resp  # Update the reactive path
            self.check_paths()  # Re-check paths with the new custom path

    @on(Button.Pressed, "#generate_config")
    def generate_config(self) -> None:
        """Pushes the configuration screen."""
        self.app.push_screen(ConfigurationScreen())  # Pushing instance

    @on(Button.Pressed, "#open_editor")
    def open_editor(self) -> None:
        """Pushes the file browser/editor screen for openstack_deploy."""
        self.app.push_screen(FileBrowserEditorScreen(initial_path=self.osa_conf_dir))
