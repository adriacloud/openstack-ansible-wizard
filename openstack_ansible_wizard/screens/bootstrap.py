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

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container, HorizontalGroup, Grid
from textual import on, work
from textual.widgets import Header, Footer, Static, Select, Button, Log
from textual.screen import Screen, ModalScreen

from textual.reactive import reactive

from openstack_ansible_wizard.common import git as cm_git
from openstack_ansible_wizard.common.screens import PathInputScreen
from openstack_ansible_wizard.common import utils
from openstack_ansible_wizard.screens.git import GitCloneScreen

OSA_REPOSITORY = "https://opendev.org/openstack/openstack-ansible"
RELEASES_REPOSITORY = "https://opendev.org/openstack/releases/raw"


class CloneOSAScreen(Screen):
    """A screen for the user to input a custom path."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("p", "change_path", "Change path"),
    ]

    clone_destination_text = reactive("")
    repository_check_text = reactive("")
    clone_path = reactive("")

    def __init__(self,
                 clone_path: str,
                 name: str | None = None,
                 id: str | None = None,
                 classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.clone_path = clone_path
        self.clone_version = int()
        self.initial_clone_version = int()
        self.force_clone = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the path input screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield Static("Clone and Bootstrap OpenStack-Ansible", classes="title")
            yield Static("Checking for available versions and local state", classes="status-message")
            yield Static("", id="clone_destination", classes="status-message")
            yield Static("", id="repository_check", classes="status-message")
            with HorizontalGroup(classes="select-row"):
                yield Select((), prompt="Select OpenStack Release", disabled=True,
                             classes="version-selector", id="openstack-version")
                yield Select((), prompt="Select OpenStack-Ansible Version", disabled=True,
                             classes="version-selector", id="openstack-ansible-version")
                yield Button("Clone", id="clone_repo", variant="primary", disabled=True)
            with HorizontalGroup(id="clone-buttons"):
                yield Button("Change version", id="change_version", variant="default")
                yield Button("Run", id="bootstrap_osa", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.check_clone()

    def on_screen_resume(self) -> None:
        """Called when this screen becomes the active screen again."""
        self.check_clone()

    def watch_clone_destination_text(self):
        self.query_one("#clone_destination", Static).update(self.clone_destination_text)

    def watch_repository_check_text(self):
        self.query_one("#repository_check", Static).update(self.repository_check_text)

    def check_clone(self) -> None:
        self.add_class('no-version-fetch')
        self.add_class('no-version-selected')
        self.add_class('no-osa-version-selected')
        self.add_class('no-clone-detected')

        if self.check_path_is_clone_destination():
            self.repository_check_text = 'Checking for currently maintained releases'
            self.fetch_openstack_releases()
            self.repository_check_text = ''

        elif self.check_path_is_osa_dir():
            osa_version = cm_git.get_git_version(self.clone_path)
            osa_version = self.initial_clone_version = cm_git.get_git_version(self.clone_path)
            self.clone_version = osa_version
            self.repository_check_text = f'Detected OpenStack-Ansible version: {osa_version}'
            self.remove_class('no-clone-detected')
        # self.dismiss(self.clone_path)

    @work(thread=True)
    def fetch_openstack_releases(self) -> None:
        self.repository_check_text = '[yellow]Checking for currently maintained releases[/yellow]'
        releases = utils.get_openstack_series(RELEASES_REPOSITORY)
        if len(releases) > 0:
            openstack_versions_widget = self.query_one("#openstack-version", Select)
            openstack_versions_widget.disabled = False
            openstack_versions_widget.set_options(
                (f"{release['release-id']} ({release['name']})", release['name']) for release in releases
            )
            self.remove_class('no-version-fetch')
            self.repository_check_text = ""

        else:
            self.repository_check_text = '[red]Failed to fetch currently supported OpenStack releases[/red]'

    @work(thread=True)
    @on(Select.Changed, '#openstack-version')
    def fetch_osa_releases(self, event: Select.Changed) -> None:
        if event.value == Select.BLANK:
            return
        self.repository_check_text = f"[yellow]Fetching versions for {event.value}...[/yellow]"
        self.selected_series = event.value
        versions = utils.get_osa_versions(RELEASES_REPOSITORY, event.value)
        if versions:
            osa_versions_widget = self.query_one("#openstack-ansible-version", Select)
            self.remove_class('no-version-selected')
            osa_versions_widget.set_options((version, version) for version in versions)
            osa_versions_widget.disabled = False
            self.repository_check_text = ""
        else:
            self.repository_check_text = "[red]Unable to fetch OpenStack-Ansible versions " \
                                         "for the {event.value} release[/red]"

    @on(Select.Changed, '#openstack-ansible-version')
    def enable_clone_button(self, event: Select.Changed) -> None:
        if event.value == Select.BLANK:
            return
        clone_repo_button_widget = self.query_one("#clone_repo", Button)
        self.remove_class('no-osa-version-selected')
        if self.check_path_is_clone_destination():
            clone_repo_button_widget = self.query_one("#clone_repo", Button)
        if self.force_clone:
            clone_repo_button_widget.label = "Re-clone"
            clone_repo_button_widget.variant = "error"
        if self.check_path_is_clone_destination() or self.initial_clone_version != event.value:
            clone_repo_button_widget.disabled = False
            self.clone_version = event.value
            self.repository_check_text = ""
        elif self.initial_clone_version == event.value:
            clone_repo_button_widget.disabled = True
            self.repository_check_text = (
                f"[yellow]Version {event.value} is already checked out. "
                "Select a different version to re-clone.[/yellow]"
            )

    @on(Button.Pressed, "#clone_repo")
    async def action_clone_repo(self) -> None:
        """Pushes screen with Clone status UI"""
        await self.app.push_screen_wait(
            GitCloneScreen(
                repo_url=OSA_REPOSITORY,
                repo_path=self.clone_path,
                version=self.clone_version,
            )
        )

    @on(Button.Pressed, "#change_version")
    def on_change_version_pressed(self) -> None:
        """Shows the version selection widgets to allow cloning a different version."""
        self.repository_check_text = 'Checking for currently maintained releases'
        self.force_clone = True
        self.fetch_openstack_releases()
        self.repository_check_text = ''

    @on(Button.Pressed, "#bootstrap_osa")
    async def action_bootstrap_osa(self) -> None:
        await self.app.push_screen_wait(
            BootstrapOsaSreen(
                path=self.clone_path,
            )
        )

    def check_path_is_clone_destination(self) -> bool:
        path = Path(self.clone_path)
        if path.exists():
            if not Path(f'{self.clone_path}/osa_toolkit/generate.py').exists():
                self.clone_destination_text = f"[red]✗[/red] {self.clone_path} already exist. " \
                    "Select a different clone path by pressing 'p'"
            return False
        elif not utils.path_writable(path, parent=True):
            self.clone_destination_text = f"[red]✗[/red] {self.clone_path} is not writtable. " \
                "Select a different clone path by pressing 'p'"
            return False
        else:
            self.clone_destination_text = f"[green]✓[/green] {self.clone_path} can be used as clone destination."
            return True

    def check_path_is_osa_dir(self) -> bool:
        path = Path(self.clone_path)
        if path.exists():
            if Path(f'{self.clone_path}/osa_toolkit/generate.py').is_file():
                self.clone_destination_text = \
                    f"[green]✓[/green] {self.clone_path} is a valid OpenStack-Ansible directory."
                return True
        return False

    @work
    async def action_change_path(self) -> None:
        """Pushes the screen to enter a custom path and awaits the result."""
        custom_osa_path_resp = await self.app.push_screen_wait(
            PathInputScreen(path_type="openstack-ansible", reversed_checks=True)
        )
        if custom_osa_path_resp:
            self.clone_path = custom_osa_path_resp
            self.check_clone()

    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.dismiss(None)


class BootstrapOsaSreen(ModalScreen):
    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("b", "bootstrap", "Bootstrap")
    ]
    status_message = reactive("")

    def __init__(self,
                 path: str,
                 name: str | None = None,
                 id: str | None = None,
                 classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.osa_path = path
        self.version = cm_git.get_git_version(path)

    def compose(self) -> ComposeResult:
        yield Grid(
            Static("Bootstrapping OpenStack-Ansible", classes="title", id="bootstrap-title"),
            Static("", id="osa-bootstrap-status-message", classes="modal-status-message-4"),
            Log(id="osa-bootstrap-progress", auto_scroll=True, highlight=True),
            Grid(
                Button("Confirm", variant="primary", id="confirm-osa-bootstrap", classes="confirm-button"),
                Button.warning("Cancel", id="cancel-osa-bootstrap", classes="confirm-button"),
                Button.success("OK", id="accept-osa-bootstrap", classes="confirm-button"),
                id="osa-bootstrap-button-row"
            ),
            id="confirm_bootstrap_dialog"
        )

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.add_class("no-bootstrap-confirm")
        self.status_message = f"Confirm proceeding with OpenStack-Ansible bootstrap of {self.version}"

    def watch_status_message(self, message: str) -> None:
        self.query_one("#osa-bootstrap-status-message", Static).update(message)

    @work
    @on(Button.Pressed, "#confirm-osa-bootstrap")
    async def action_bootstrap(self) -> None:
        self.remove_class("no-bootstrap-confirm")
        self.add_class("bootstrap-confirmed")
        log_widget = self.query_one("#osa-bootstrap-progress", Log)
        self.status_message = "[yellow]Running bootstrap-ansible.sh...[/yellow]"
        log_widget.clear()
        try:
            proc = await asyncio.create_subprocess_shell(
                f"{self.osa_path}/scripts/bootstrap-ansible.sh",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.osa_path,
            )
            async for line in proc.stdout:
                log_widget.write_line(line.decode(errors="replace").rstrip())
            rc = await proc.wait()
            if rc == 0:
                self.status_message = "[green]Bootstrap completed successfully.[/green]"
            else:
                self.status_message = f"[red]Bootstrap failed (exit code {rc}).[/red]"
        except Exception as e:
            self.status_message = f"[red]Error running bootstrap script: {e}[/red]"
        log_widget.scroll_end(animate=False)
        self.add_class("bootstrap-completed")

    @on(Button.Pressed, "#cancel-osa-bootstrap")
    @on(Button.Pressed, "#accept-osa-bootstrap")
    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.dismiss(None)
