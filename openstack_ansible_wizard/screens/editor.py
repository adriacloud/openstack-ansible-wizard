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
from textual.containers import VerticalScroll, HorizontalGroup, HorizontalScroll, Grid
from textual import on, work
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets.tree import TreeNode
from textual.widgets import Header, Footer, Button, Static, DirectoryTree, Input, RadioSet, RadioButton
from openstack_ansible_wizard.common.screens import ConfirmExitScreen, WizardConfigScreen
from openstack_ansible_wizard.extensions.textarea import YAMLTextArea


class FileBrowserEditorScreen(WizardConfigScreen):
    """A screen displaying a directory tree and a text editor."""

    BINDINGS = WizardConfigScreen.BINDINGS + [
        ("n", "create_new", "Create New"),
        ("delete", "delete_file", "Delete"),
    ]

    selected_path: reactive[Path | None] = reactive(None)

    def __init__(self, initial_path: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.initial_path = initial_path
        self.original_content: str | None = None
        self._ignore_selection_change = False

    @staticmethod
    def _editor_theme(current_theme):
        if current_theme.dark:
            return "vscode_dark"
        else:
            return "github_light"

    def compose(self) -> ComposeResult:
        """Create child widgets for the file browser/editor screen."""
        yield Header()
        with HorizontalGroup(classes="editor-layout"):
            with VerticalScroll(classes="sidebar"):
                yield DirectoryTree(self.initial_path, id="file_tree")
            with VerticalScroll(classes="main-content"):
                yield Static("Select a file from the tree to edit.", id="editor_status")
                yield YAMLTextArea.code_editor(id="text_editor", language="yaml", show_line_numbers=True)
                with HorizontalScroll(classes="content-buttons"):
                    yield Button("New", id="new_button", variant="primary")
                    yield Button("Save File", id="save_button", variant="success")
                    yield Button.warning("Delete File", id="delete_button")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.add_class("no-file")
        editor = self.query_one("#text_editor", YAMLTextArea)
        editor.disabled = True  # Disable until a file is loaded
        editor.theme = self._editor_theme(self.app.current_theme)
        self.query_one("#save_button", Button).disabled = True
        self.query_one("#delete_button", Button).disabled = True

    @work
    async def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handles selection of a file in the DirectoryTree, confirming if there are unsaved changes."""
        if self._ignore_selection_change:
            self._ignore_selection_change = False
            return

        # Handle unsaved changes before proceeding.
        if not await self._handle_unsaved_changes():
            return

        self.selected_path = event.path
        editor = self.query_one("#text_editor", YAMLTextArea)
        save_button = self.query_one("#save_button", Button)
        delete_button = self.query_one("#delete_button", Button)
        status_message = self.query_one("#editor_status", Static)
        self.remove_class("directory-selected")

        try:
            with open(self.selected_path, "r") as f:
                content = f.read()
            self.original_content = content
            editor.load_text(content)
            editor.disabled = False
            save_button.disabled = False
            delete_button.label = "Delete File"
            delete_button.disabled = False
            self.remove_class("no-file")
            status_message.update(f"Editing: [green]{self.selected_path}[/green]")
        except Exception as e:
            self.original_content = None
            editor.load_text(f"Could not open file: {e}")
            editor.disabled = True
            save_button.disabled = True
            delete_button.disabled = True
            self.add_class("no-file")
            status_message.update(f"[red]Error:[/red] Could not open {self.selected_path}")
            self.log(f"Error opening file {self.selected_path}: {e}")

    @work
    async def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handles selection of a directory, confirming if there are unsaved changes."""
        if self._ignore_selection_change:
            self._ignore_selection_change = False
            return

        # Handle unsaved changes before proceeding.
        if not await self._handle_unsaved_changes():
            return

        self.selected_path = event.path
        editor = self.query_one("#text_editor", YAMLTextArea)
        save_button = self.query_one("#save_button", Button)
        delete_button = self.query_one("#delete_button", Button)
        status_message = self.query_one("#editor_status", Static)

        self.original_content = None
        editor.load_text("")
        editor.disabled = True
        save_button.disabled = True
        delete_button.label = "Delete Directory"
        delete_button.disabled = False
        self.add_class("no-file")
        self.add_class("directory-selected")
        status_message.update(f"Selected directory: [green]{self.selected_path}[/green]")

    @on(Button.Pressed, "#save_button")
    def action_save_configs(self) -> None:
        """Saves the current content of the editor to the file."""
        if self.selected_path and self.selected_path.is_file():
            editor = self.query_one("#text_editor", YAMLTextArea)
            status_message = self.query_one("#editor_status", Static)
            try:
                with open(self.selected_path, "w") as f:
                    f.write(editor.text)
                self.original_content = editor.text  # Update original content on save
                status_message.update(f"[green]File saved successfully:[/green] {self.selected_path}")
            except Exception as e:
                status_message.update(f"[red]Error saving file:[/red] {e}")
                self.log(f"Error saving file {self.selected_path}: {e}")
        else:
            self.query_one("#editor_status", Static).update("[yellow]No file selected to save.[/yellow]")

    @work
    @on(Button.Pressed, "#new_button")
    async def action_create_new(self) -> None:
        """Pushes a screen to create a new file or directory."""
        base_path = self.initial_path
        if self.selected_path and self.selected_path.is_dir():
            base_path = self.selected_path
        elif self.selected_path and self.selected_path.is_file():
            base_path = self.selected_path.parent

        result = await self.app.push_screen_wait(CreateNewEntryScreen(base_path=Path(base_path)))
        status_message = self.query_one("#editor_status", Static)
        self.log(f"creation result is {result}")
        if result:
            name, entry_type = result
            new_path = Path(base_path) / name
            status_message.update(
                f"[green]Successfully created {entry_type}:[/green] {new_path}")
            self.query_one("#file_tree", DirectoryTree).reload()
        else:
            status_message.update("[yellow]New entry creation cancelled.[/yellow]")

    @work
    @on(Button.Pressed, "#delete_button")
    async def action_delete_file(self) -> None:
        """Deletes the currently selected file after confirmation."""
        if not self.selected_path:
            self.query_one("#editor_status", Static).update("[yellow]No file or directory selected to delete.[/yellow]")
            return

        confirm_message = f"Are you sure you want to delete '{self.selected_path.name}'?"
        confirmed = await self.app.push_screen_wait(ConfirmExitScreen(confirm_message))

        status_message = self.query_one("#editor_status", Static)
        if confirmed:
            try:
                # Check if it's a file or directory before unlinking (files) or rmdir (empty dirs)
                if self.selected_path.is_file():
                    self.selected_path.unlink()
                    status_message.update(f"[green]File deleted successfully:[/green] {self.selected_path.name}")
                elif self.selected_path.is_dir():
                    # For a directory, it must be empty to be deleted with rmdir()
                    self.selected_path.rmdir()
                    status_message.update(
                        f"[green]Directory deleted successfully:[/green] {self.selected_path.name}")
                else:
                    status_message.update(f"[red]Error:[/red] Cannot delete '{self.selected_path.name}'."
                                          "Not a file or empty directory.")
                    return

                # Clear editor and disable buttons as the file is gone
                editor = self.query_one("#text_editor", YAMLTextArea)
                editor.load_text("")
                editor.disabled = True
                self.query_one("#save_button", Button).disabled = True
                delete_button = self.query_one("#delete_button", Button)
                delete_button.disabled = True
                delete_button.label = "Delete"
                self.remove_class("directory-selected")
                self.add_class("no-file")
                self.selected_path = None  # Clear the current file selection
                self.query_one("#file_tree", DirectoryTree).reload()  # Reload the tree
            except OSError as e:
                status_message.update(f"[red]Error deleting[/red] {e.filename}:\n[red]{e.strerror}[/red]")
                self.log(f"Error deleting {self.selected_path}: {e}")
            except Exception as e:
                status_message.update(f"[red]An unexpected error occurred:[/red] {e}")
                self.log(f"Unexpected error deleting {self.selected_path}: {e}")
        else:
            status_message.update("[yellow]Deletion cancelled.[/yellow]")

    def has_unsaved_changes(self) -> bool:
        """Check if the editor content has changed since it was loaded or saved."""
        if self.selected_path and self.selected_path.is_file() and self.original_content is not None:
            editor = self.query_one("#text_editor", YAMLTextArea)
            return editor.text != self.original_content
        return False

    async def _handle_unsaved_changes(self) -> bool:
        """
        Checks for unsaved changes and prompts the user if necessary.
        Returns True if the operation should proceed, False otherwise.
        """
        if not self.has_unsaved_changes():
            return True

        tree = self.query_one("#file_tree", DirectoryTree)
        path_before_selection = self.selected_path

        message = "You have unsaved changes.\nDiscard changes and continue?"
        proceed = await self.app.push_screen_wait(ConfirmExitScreen(message=message))

        if not proceed:
            # User cancelled. Revert the logical path and restore the visual cursor.
            self.selected_path = path_before_selection
            node_to_restore = self._find_node_by_path(path_before_selection)
            if node_to_restore:
                self._ignore_selection_change = True
                tree.select_node(node_to_restore)
            return False
        return True

    def _find_node_by_path(self, target_path: Path | None) -> TreeNode | None:
        """Recursively search for a DirectoryTree node by its path."""
        if not target_path:
            return None

        tree = self.query_one("#file_tree", DirectoryTree)

        def search(node: TreeNode) -> TreeNode | None:
            if node.data and node.data.path == target_path:
                return node
            for child in node.children:
                found = search(child)
                if found:
                    return found
            return None

        return search(tree.root)


class CreateNewEntryScreen(ModalScreen):
    """A screen for the user to input a new file or directory name and type."""

    BINDINGS = [
        ("escape", "dismiss_none", "Cancel"),
    ]

    def __init__(self, base_path: Path, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.base_path = base_path

    def compose(self) -> ComposeResult:
        """Create child widgets for the new entry screen."""
        yield Grid(
            Static(
                f"Create New Entry in:\n[green]{self.base_path}[/green]",
                classes="title", id="create_entry_message"),
            Input(placeholder="Enter name (e.g., my_file.yaml or new_dir)", id="entry_name_input"),
            RadioSet(
                RadioButton("File", id="file"),
                RadioButton("Directory", id="directory"),
                id="entry_type_radios",
                name="entry_type",
            ),
            Button("Create", id="create_entry_button", variant="primary"),
            # Static("", ),
            id="create_file_dialog"
        )

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Set the default selected radio button after composition
        self.query_one("#file", RadioButton).value = True

    @on(Input.Submitted, "#entry_name_input")
    @on(Button.Pressed, "#create_entry_button")
    def create_entry(self) -> None:
        """Processes the submitted name and type to create the entry."""
        entry_name = self.query_one("#entry_name_input", Input).value.strip()
        entry_type = self.query_one("#entry_type_radios", RadioSet).pressed_button.id
        message_widget = self.query_one("#create_entry_message", Static)

        if not entry_name:
            message_widget.update("[red]Error:[/red] Name cannot be empty.")
            return

        new_path = Path(self.base_path).joinpath(entry_name)

        if new_path.exists():
            message_widget.update(f"[red]Error:[/red] '{entry_name}' already exists.")
            return

        try:
            if entry_type == "file":
                new_path.touch()
                message_widget.update(f"[green]File '{entry_name}' created successfully.[/green]")
            elif entry_type == "directory":
                new_path.mkdir()
                message_widget.update(f"[green]Directory '{entry_name}' created successfully.[/green]")
            self.log(f"our requested type is {entry_type}")
            self.dismiss((entry_name, entry_type))  # Dismiss with success result
        except Exception as e:
            message_widget.update(f"[red]Error creating entry:[/red] {e}")
            self.log(f"Error creating entry {new_path}: {e}")

    def action_dismiss_none(self) -> None:
        """Dismisses the screen with no result (cancel)."""
        self.dismiss(None)
