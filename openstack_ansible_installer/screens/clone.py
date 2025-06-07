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
from textual.containers import Container, HorizontalGroup
from textual import on, work
from textual.widgets import Header, Footer, Static, Select, Button
from textual.screen import Screen

from textual.reactive import reactive

from common import utils
from screens.git import GitCloneScreen
from screens.path_selector import PathInputScreen

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

    def compose(self) -> ComposeResult:
        """Create child widgets for the path input screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield Static("Clone OpenStack-Ansible UI", classes="title")
            yield Static("Checking for available versions and local state", classes="status_message")
            yield Static("", id="clone_destination", classes="status_message")
            yield Static("", id="repository_check", classes="status_message")
            with HorizontalGroup(classes="select-row"):
                yield Select((), prompt="Select OpenStack Release", disabled=True,
                             classes="version-selector", id="openstack-version")
                yield Select((), prompt="Select OpenStack-Ansible Version", disabled=True,
                             classes="version-selector", id="openstack-ansible-version")
                yield Button("Clone", id="clone_repo", variant="primary", disabled=True)
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
        self.check_path()
        self.repository_check_text = 'Checking currently for maintained releases'
        self.fetch_openstack_releases()
        self.repository_check_text = ''

        # self.dismiss(self.clone_path)

    @work
    async def fetch_openstack_releases(self) -> None:
        self.repository_check_text = '[yellow]Checking currently for maintained releases[/yellow]'
        releases = await utils.get_openstack_series(RELEASES_REPOSITORY)
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

    @work
    @on(Select.Changed, '#openstack-version')
    async def fetch_osa_releases(self, event: Select.Changed) -> None:
        self.repository_check_text = '[yellow]Please select OpenStack release again[/yellow]'
        if event.value == Select.BLANK:
            return
        self.selected_series = event.value
        versions = await utils.get_osa_versions(RELEASES_REPOSITORY, event.value)
        if versions:
            osa_versions_widget = self.query_one("#openstack-ansible-version", Select)
            self.remove_class('no-version-selected')
            osa_versions_widget.set_options((version, version) for version in versions)
            osa_versions_widget.disabled = False
            self.repository_check_text = ""
        else:
            self.repository_check_text = "[red]Unable to fetch OpenStack-Ansible versions for the release[/red]"

    @on(Select.Changed, '#openstack-ansible-version')
    def enable_clone_button(self, event: Select.Changed) -> None:
        if event.value == Select.BLANK:
            return
        self.remove_class('no-osa-version-selected')
        if self.check_path():
            clone_repo_button_widget = self.query_one("#clone_repo", Button)
            clone_repo_button_widget.disabled = False
            self.clone_version = event.value

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

    def check_path(self) -> bool:
        path = Path(self.clone_path)
        if path.exists():
            self.clone_destination_text = f"[red]✗[/red] {self.clone_path} already exist." \
                "Select a different path by pressing 'p'"
            return False
        elif not utils.path_writable(path, parent=True):
            self.clone_destination_text = f"[red]✗[/red] {self.clone_path} is not writtable." \
                "Select a different path by pressing 'p'"
            return False
        else:
            self.clone_destination_text = f"[green]✓[/green] {self.clone_path} can be used as destination."
            return True

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
