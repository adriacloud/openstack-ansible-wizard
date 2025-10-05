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
from shutil import copy as file_copy
from subprocess import run as p_run
from sys import executable as py_exec

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, HorizontalGroup
from textual.widgets import Header, Footer, Button, Static
from textual.reactive import reactive
from textual.screen import Screen

from openstack_ansible_wizard.screens.bootstrap import CloneOSAScreen
from openstack_ansible_wizard.screens.editor import FileBrowserEditorScreen
from openstack_ansible_wizard.screens.inventory import InventoryScreen
from openstack_ansible_wizard.screens.networks import NetworkScreen
from openstack_ansible_wizard.screens.service import ServicesMainScreen
from openstack_ansible_wizard.common.screens import ConfirmExitScreen, PathInputScreen


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
            yield Static("OpenStack-Ansible Wizard", classes="title")
            yield Static("Checking for existing setup...", id="status_message", classes="status-message")
            yield Static("", id="osa_path_status", classes="status-message")
            yield Static("", id="etc_path_status", classes="status-message")
            with HorizontalGroup(classes="button-row"):
                yield Button("Bootstrap", id="clone_osa", variant="primary", disabled=True)
                yield Button("Custom OpenStack-Ansible Path", id="custom_osa_path", variant="default", disabled=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Initialize", id="init_config_dir", variant="success", disabled=True)
                yield Button("Editor", id="open_editor", variant="warning", disabled=True)
                yield Button("Custom Configuation Path", id="custom_config_path", variant="default", disabled=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Inventory configuration", id="inventory_config", variant="primary", disabled=True)
                yield Button("Network configuration", id="network_config", variant="primary", disabled=True)
                yield Button("Service configuration", id="service_config", variant="primary", disabled=True)
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
        proceed_config_button = self.query_one("#inventory_config", Button)
        proceed_network_button = self.query_one("#network_config", Button)
        proceed_service_button = self.query_one("#service_config", Button)
        init_config_button = self.query_one("#init_config_dir", Button)
        custom_config_button = self.query_one("#custom_config_path", Button)
        open_editor_button = self.query_one("#open_editor", Button)

        # init_config_button.display = False
        check_osa_success = False
        check_config_success = False

        if osa_path.is_dir():
            if Path(f'{self.osa_clone_dir}/osa_toolkit/generate.py').is_file():
                osa_status_widget.update(f"[green]✓[/green] {self.osa_clone_dir} exists.")
                clone_button.disabled = False
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
            if Path(f'{self.osa_conf_dir}/openstack_user_config.yml').is_file():
                etc_status_widget.update(f"[green]✓[/green] {self.osa_conf_dir} exists.")
                status_message_widget.update("")
                status_message_widget.display = False
                proceed_config_button.disabled = True
                proceed_network_button.disabled = True
                proceed_service_button.disabled = True
                init_config_button.display = False
                open_editor_button.disabled = False
                check_config_success = True
            else:
                etc_status_widget.update(f"[red]✗[/red] {self.osa_conf_dir} exists but is not yet initialized.")
                proceed_config_button.disabled = True
                proceed_config_button.display = False
                proceed_network_button.disabled = True
                proceed_network_button.display = False
                proceed_service_button.disabled = True
                proceed_service_button.display = False
                open_editor_button.disabled = False
                custom_config_button.disabled = False
                init_config_button.disabled = False
                init_config_button.display = True
        else:
            etc_status_widget.update(f"[red]✗[/red] {self.osa_conf_dir} does not exist.")
            if osa_path.is_dir():  # Only suggest config if OSA repo is found
                status_message_widget.update(f"No {self.osa_conf_dir} found. Proceed to configuration.")
                custom_config_button.disabled = False
                init_config_button.disabled = False
                init_config_button.display = True
            proceed_config_button.disabled = True
            proceed_config_button.display = False
            proceed_network_button.disabled = True
            proceed_network_button.display = False
            proceed_service_button.disabled = True
            proceed_service_button.display = False
            open_editor_button.disabled = True
            open_editor_button.display = False

        if check_osa_success and check_config_success:
            # Automatically switch to editor if all required settings exist
            # self.call_after_refresh(lambda: self.app.push_screen(FileBrowserEditorScreen(initial_path=str(etc_path))))
            open_editor_button.disabled = False
            proceed_config_button.disabled = False
            proceed_config_button.display = True
            proceed_network_button.disabled = False
            proceed_network_button.display = True
            proceed_service_button.disabled = False
            proceed_service_button.display = True
            custom_config_button.disabled = False
            open_editor_button.display = True
            init_config_button.display = False

    @on(Button.Pressed, "#clone_osa")
    @work
    async def clone_repo(self) -> None:
        """Simulates cloning the OpenStack-Ansible repository."""
        osa_cloned = await self.app.push_screen_wait(CloneOSAScreen(clone_path=self.osa_clone_dir))
        if osa_cloned:
            # Update the reactive path is likely not needed as we're passing reactive object to the screen
            self.osa_clone_dir = osa_cloned
            self.check_paths()  # Re-check paths with the new custom path

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

    @on(Button.Pressed, "#inventory_config")
    def configure_inventory(self) -> None:
        """Pushes the inventory configuration screen."""
        self.app.push_screen(InventoryScreen(config_path=self.osa_conf_dir, osa_path=self.osa_clone_dir))

    @on(Button.Pressed, "#network_config")
    def configure_networks(self) -> None:
        """Pushes the network configuration screen."""
        self.app.push_screen(NetworkScreen(config_path=self.osa_conf_dir, osa_path=self.osa_clone_dir))

    @on(Button.Pressed, "#service_config")
    def configure_services(self) -> None:
        """Pushes the main service configuration screen."""
        self.app.push_screen(ServicesMainScreen(config_path=self.osa_conf_dir, osa_path=self.osa_clone_dir))

    @on(Button.Pressed, "#open_editor")
    def open_editor(self) -> None:
        """Pushes the file browser/editor screen for openstack_deploy."""
        self.app.push_screen(FileBrowserEditorScreen(initial_path=self.osa_conf_dir))

    @on(Button.Pressed, "#init_config_dir")
    @work
    async def initialized_osa_config_dir(self):
        """Pushes confirmation screen about the config dir init"""
        message = f"Are you sure you want to initialize {self.osa_conf_dir} as OSA_CONFIG_DIR?"
        init_confirm_result = await self.app.push_screen_wait(ConfirmExitScreen(message=message))
        if init_confirm_result:
            conf_dir_path = Path(self.osa_conf_dir)
            init_directories = [
                conf_dir_path,
                conf_dir_path / "conf.d",
                conf_dir_path / "env.d",
                conf_dir_path / "group_vars",
                conf_dir_path / "group_vars" / "all",
                conf_dir_path / "host_vars"
            ]
            for dir in init_directories:
                dir.mkdir(exist_ok=True)

            (conf_dir_path / "openstack_user_config.yml").touch(exist_ok=True)

            # Copy user_secrets.yml from the OSA repository
            source_secrets_file = Path(self.osa_clone_dir) / "etc" / "openstack_deploy" / "user_secrets.yml"
            dest_secrets_file = conf_dir_path / "user_secrets.yml"
            if source_secrets_file.exists() and not dest_secrets_file.exists():
                file_copy(source_secrets_file, dest_secrets_file)
                p_run([
                    py_exec,
                    f"{self.osa_clone_dir}/scripts/pw-token-gen.py",
                    "--file",
                    str(dest_secrets_file)
                ])
            self.check_paths()
