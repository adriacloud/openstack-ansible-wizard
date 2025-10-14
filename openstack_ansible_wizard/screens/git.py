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
import git
from git import RemoteProgress

from textual.app import ComposeResult
from textual.containers import Grid
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import ProgressBar, Static, Button
from textual import on, work

import os
import shutil


class GitCloneProgress(RemoteProgress):
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback

    def update(self, op_code, cur_count, max_count=None, message=''):
        op_id = op_code & self.OP_MASK
        stage = ""
        if op_id == self.COUNTING:
            stage = "Counting objects"
        elif op_id == self.COMPRESSING:
            stage = "Compressing objects"
        elif op_id == self.RECEIVING:
            stage = "Receiving objects"
        elif op_id == self.RESOLVING:
            stage = "Resolving deltas"
        elif op_id == self.FINDING_SOURCES:
            stage = "Finding sources"
        elif op_id == self.REPORTING:
            stage = "Reporting"
        else:
            # Fallback for unknown operation IDs.
            stage = f"Processing ({op_id})"

        if max_count:
            self.update_callback(cur_count, max_count, stage)


class GitCloneScreen(ModalScreen):
    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("s", "start", "Start")
    ]
    progress = reactive(0)
    max_progress = reactive(100)

    def __init__(self,
                 repo_url: str,
                 repo_path: str,
                 version: str,
                 branch: str = 'master',
                 name: str | None = None,
                 id: str | None = None,
                 classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.branch = branch
        self.version = version

    def compose(self) -> ComposeResult:
        yield Grid(
            Static("Clone OpenStack-Ansible repository", classes="title"),
            Static(f"Confirm clonning OpenStack-Ansible {self.version} to {self.repo_path}",
                   id="git-clone-status-message", classes="modal-status-message-4"),
            ProgressBar(
                total=self.max_progress,
                show_percentage=True,
                show_eta=False,
                id="git-clone-progress"),
            Grid(
                Button("Confirm", variant="primary", id="confirm-git-clone", classes="confirm-button"),
                Button.warning("Cancel", id="cancel-git-clone", classes="confirm-button"),
                Button.success("OK", id="accept-git-clone", classes="confirm-button"),
                id="git-clone-button-row"
            ),
            id="confirm_clone_dialog"
        )

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.add_class("no-clone-confirm")

    @work
    @on(Button.Pressed, "#confirm-git-clone")
    async def action_start(self) -> None:
        self.remove_class("no-clone-confirm")
        self.add_class("clone-confirmed")
        progress_bar = self.query_one("#git-clone-progress", ProgressBar)
        static_message = self.query_one("#git-clone-status-message", Static)
        static_message.update("Cloning Repository...")

        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)

        def update_bar(cur, max_, stage):
            self.progress = cur
            self.max_progress = max_
            progress_bar.update(total=max_, progress=cur)
            static_message.update(stage)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: git.Repo.clone_from(
                self.repo_url,
                self.repo_path,
                branch=self.branch,
                progress=GitCloneProgress(update_bar)
            )
        )
        static_message.update(f"Checking out to {self.version}")
        if self.version:
            git.Git(self.repo_path).checkout(self.version)
        progress_bar.update(total=self.max_progress, progress=self.max_progress)
        static_message.update("Clone Complete ✅")
        self.add_class("clone-completed")

    @on(Button.Pressed, "#cancel-git-clone")
    @on(Button.Pressed, "#accept-git-clone")
    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.dismiss(None)
