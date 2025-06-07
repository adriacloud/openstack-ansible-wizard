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
from textual.screen import Screen, ModalScreen
from textual.widgets import Header, Footer, Button, Static, DirectoryTree, Input, RadioSet, RadioButton, Label

from extensions.button import NavigableButton
from extensions.textarea import YAMLTextArea


class FileBrowserEditorScreen(Screen):
    """A screen displaying a directory tree and a text editor."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("s", "save_file", "Save File"),
        ("n", "create_new", "Create New"),
        ("delete", "delete_file", "Delete"),
    ]

    current_file_path = reactive(None)

    def __init__(self, initial_path: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.initial_path = initial_path

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
                    yield Button.success("Save File", id="save_button")
                    yield Button.warning("Delete File", id="delete_button")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        self.add_class("no-file")
        editor = self.query_one("#text_editor", YAMLTextArea)
        editor.disabled = True  # Disable until a file is loaded
        editor.theme = self._editor_theme(self.app.current_theme)
        self.query_one("#save_button", Button).disabled = True

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Loads the content of the selected file into the text editor."""
        self.current_file_path = event.path
        editor = self.query_one("#text_editor", YAMLTextArea)
        editor.theme = self._editor_theme(self.app.current_theme)
        save_button = self.query_one("#save_button", Button)
        delete_button = self.query_one("#delete_button", Button)
        status_message = self.query_one("#editor_status", Static)
        try:
            with open(self.current_file_path, "r") as f:
                content = f.read()
            editor.load_text(content)
            editor.disabled = False
            save_button.disabled = False
            delete_button.disabled = False
            self.add_class("file-selected")
            status_message.update(f"Editing: [green]{self.current_file_path}[/green]")
        except Exception as e:
            editor.load_text(f"Could not open file: {e}")
            editor.disabled = True
            save_button.disabled = True
            delete_button.disabled = True
            self.add_class("no-file")
            status_message.update(f"[red]Error:[/red] Could not open {self.current_file_path}")
            self.log(f"Error opening file {self.current_file_path}: {e}")

    @on(Button.Pressed, "#save_button")
    def action_save_file(self) -> None:
        """Saves the current content of the editor to the file."""
        if self.current_file_path:
            editor = self.query_one("#text_editor", YAMLTextArea)
            status_message = self.query_one("#editor_status", Static)
            try:
                with open(self.current_file_path, "w") as f:
                    f.write(editor.text)
                status_message.update(f"[green]File saved successfully:[/green] {self.current_file_path}")
            except Exception as e:
                status_message.update(f"[red]Error saving file:[/red] {e}")
                self.log(f"Error saving file {self.current_file_path}: {e}")
        else:
            self.query_one("#editor_status", Static).update("[yellow]No file selected to save.[/yellow]")

    @work
    @on(Button.Pressed, "#new_button")
    async def action_create_new(self) -> None:
        """Pushes a screen to create a new file or directory."""
        result = await self.app.push_screen_wait(CreateNewEntryScreen(base_path=self.initial_path))
        status_message = self.query_one("#editor_status", Static)
        self.log(f"creation result is {result}")
        if result:
            name, entry_type = result
            status_message.update(f"[green]Successfully created {entry_type}:[/green] {self.initial_path}/{name}")
            self.query_one("#file_tree", DirectoryTree).reload()
        else:
            status_message.update("[yellow]New entry creation cancelled.[/yellow]")

    @work
    @on(Button.Pressed, "#delete_button")
    async def action_delete_file(self) -> None:
        """Deletes the currently selected file after confirmation."""
        if not self.current_file_path:
            self.query_one("#editor_status", Static).update("[yellow]No file selected to delete.[/yellow]")
            return

        confirm_message = f"Are you sure you want to delete '{self.current_file_path.name}'?"
        confirmed = await self.app.push_screen_wait(ConfirmScreen(confirm_message))

        status_message = self.query_one("#editor_status", Static)
        if confirmed:
            try:
                # Check if it's a file or directory before unlinking (files) or rmdir (empty dirs)
                if self.current_file_path.is_file():
                    self.current_file_path.unlink()
                    status_message.update(f"[green]File deleted successfully:[/green] {self.current_file_path.name}")
                elif self.current_file_path.is_dir():
                    # For a directory, it must be empty to be deleted with rmdir()
                    self.current_file_path.rmdir()
                    status_message.update(
                        f"[green]Directory deleted successfully:[/green] {self.current_file_path.name}")
                else:
                    status_message.update(f"[red]Error:[/red] Cannot delete '{self.current_file_path.name}'."
                                          "Not a file or empty directory.")
                    return

                # Clear editor and disable buttons as the file is gone
                editor = self.query_one("#text_editor", YAMLTextArea)
                editor.load_text("")
                editor.disabled = True
                self.query_one("#save_button", Button).disabled = True
                self.query_one("#delete_button", Button).disabled = True
                self.add_class("no-file")
                self.current_file_path = None  # Clear the current file selection
                self.query_one("#file_tree", DirectoryTree).reload()  # Reload the tree
            except OSError as e:
                status_message.update(f"[red]Error deleting:[/red] {e}")
                self.log(f"Error deleting {self.current_file_path}: {e}")
            except Exception as e:
                status_message.update(f"[red]An unexpected error occurred:[/red] {e}")
                self.log(f"Unexpected error deleting {self.current_file_path}: {e}")
        else:
            status_message.update("[yellow]Deletion cancelled.[/yellow]")

    def action_pop_screen(self) -> None:
        """Pops the current screen from the screen stack."""
        self.app.pop_screen()


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


class ConfirmScreen(ModalScreen[bool]):  # Screen[bool] indicates it dismisses with a boolean
    """A modal screen for confirming an action."""

    BINDINGS = [
        ("escape", "cancel", "Back"),
    ]

    def __init__(self, message: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.message = message

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self.message, classes="title", id="confirm_question"),
            NavigableButton.success("Yes", id="confirm_yes"),
            NavigableButton("No", id="confirm_no", variant="primary"),
            id="confirm_dialog"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm_yes":
            self.dismiss(True)
        elif event.button.id == "confirm_no":
            self.dismiss(False)

    def action_cancel(self) -> None:
        """Dismisses the screen with a False value when escape is pressed."""
        self.dismiss(False)
