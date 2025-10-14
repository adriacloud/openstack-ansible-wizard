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
from pathlib import Path
import time
import yaml

from textual.app import ComposeResult
from textual.containers import Container, Grid, VerticalScroll, HorizontalGroup
from textual.widgets import Header, Footer, Static, Button, DataTable, Input, Checkbox, Label
from textual.reactive import reactive
from textual.screen import ModalScreen
from ruamel.yaml import YAML, YAMLError
from textual import on, work

from openstack_ansible_wizard.common.screens import WizardConfigScreen


class AddHostScreen(ModalScreen):
    """A modal screen to add a new host."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(
            self, all_groups: list[str], host_data: dict | None = None,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.all_groups = sorted(all_groups)
        self.host_data = host_data

    def compose(self) -> ComposeResult:
        is_editing = self.host_data is not None
        if is_editing:
            title = "Edit Host"
            button_label = "Update Host"
            hostname = self.host_data.get("hostname", "")
            ip = self.host_data.get("ip", "")
            mgmt_ip = self.host_data.get("management_ip", "")
            host_groups = self.host_data.get("groups", [])
        else:
            title = "Add New Host"
            button_label = "Add Host"
            hostname = ""
            ip = ""
            mgmt_ip = ""
            host_groups = []

        with Grid(id="add_host_dialog", classes="modal-screen-grid"):
            yield Static(title, classes="title")
            yield Static(id="add_host_message", classes="modal-status-message-2")
            yield Label("Hostname:")
            yield Input(
                value=hostname,
                placeholder="e.g., new-compute-01",
                id="host_name_input",
                disabled=is_editing
            )
            yield Static(id="add_ipaddr_message", classes="modal-status-message-2")
            yield Label("IP Address:")
            yield Input(value=ip, placeholder="e.g., 192.168.1.100", id="ip_input")
            yield Label("Management IP (optional):")
            yield Input(value=mgmt_ip, placeholder="e.g., 10.0.0.100", id="mgmt_ip_input")
            yield Static("Assign to groups:")
            with VerticalScroll(classes="inventory-group-list"):
                for group in self.all_groups:
                    yield Checkbox(
                        group,
                        value=(group in host_groups),
                        id=f"group_{group}"
                    )
            with Grid(classes="modal-button-row"):
                yield Button(button_label, variant="primary", id="add_host_button", classes="confirm-button")
                yield Button("Cancel", id="cancel_button", classes="confirm-button")

    @on(Button.Pressed, "#add_host_button")
    def on_add_host(self) -> None:
        hostname = self.query_one("#host_name_input", Input).value.strip()
        ip = self.query_one("#ip_input", Input).value.strip()

        host_message_widget = self.query_one("#add_host_message")
        ip_message_widget = self.query_one("#add_ipaddr_message")

        if not hostname:
            host_message_widget.update("[red]Hostname cannot be empty.[/red]")
        else:
            host_message_widget.update("")
        if not ip:
            ip_message_widget.update("[red]IP Address cannot be empty.[/red]")
        else:
            ip_message_widget.update("")

        if not ip or not hostname:
            return

        new_host_data = {
            "hostname": hostname,
            "ip": ip,
            "management_ip": self.query_one("#mgmt_ip_input", Input).value.strip() or None,
            "groups": [
                cb.label.plain for cb in self.query(Checkbox) if cb.value
            ]
        }
        self.dismiss(new_host_data)

    @on(Button.Pressed, "#cancel_button")
    def action_pop_screen(self) -> None:
        self.dismiss(None)


class CreateGroupScreen(ModalScreen):
    """A modal screen to create a new host group."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, all_hosts: dict, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.all_hosts = all_hosts

    def compose(self) -> ComposeResult:
        with Grid(id="create_group_dialog", classes="modal-screen-grid"):
            yield Static("Create New Group", classes="title")
            yield Label("Group Name (e.g., 'compute'):")
            yield Input(placeholder="my-new-group", id="group_name_input")
            yield Static("Add hosts to group (optional):")
            with VerticalScroll(classes="checkbox-list"):
                if self.all_hosts:
                    for hostname in sorted(self.all_hosts.keys()):
                        yield Checkbox(hostname, id=f"host_{hostname}")
                else:
                    yield Static("No hosts defined yet.")
            with Grid(classes="modal-button-row"):
                yield Button("Add Group", variant="primary", id="create_group_button", classes="confirm-button")
                yield Button("Cancel", id="cancel_button", classes="confirm-button")

    @on(Button.Pressed, "#create_group_button")
    def on_create_group(self) -> None:
        group_name = self.query_one("#group_name_input", Input).value.strip()
        if not group_name:
            return

        selected_hosts = [cb.label.plain for cb in self.query(Checkbox) if cb.value]
        self.dismiss({"group_name": group_name, "selected_hosts": selected_hosts})

    @on(Button.Pressed, "#cancel_button")
    def action_pop_screen(self) -> None:
        self.dismiss(None)


class InventoryScreen(WizardConfigScreen):
    """A screen for managing OpenStack-Ansible host configurations."""

    BINDINGS = WizardConfigScreen.BINDINGS + [
        ("a", "add_host", "Add Host"),
        ("g", "create_group", "Create Group"),
    ]

    # This will hold the structured host data
    # Format: { "hostname": {"ip": "...", "management_ip": "...", "groups": {"group_name": "file_path.yml"}}}
    hosts_data = reactive(dict)
    all_groups = reactive(set)

    def __init__(
            self, config_path: str, osa_path: str,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.config_path = config_path
        self.osa_path = osa_path
        self.initial_hosts_data = {}
        self._last_row_click_time = 0.0
        self._last_clicked_row_key = None

    def _get_config_files(self) -> list[Path]:
        """Gathers all relevant YAML configuration files."""
        config_path = Path(self.config_path)
        files = []
        if (config_path / "openstack_user_config.yml").exists():
            files.append(config_path / "openstack_user_config.yml")

        conf_d_path = config_path / "conf.d"
        if conf_d_path.is_dir():
            files.extend(conf_d_path.glob("*.yml"))

        return files

    def compose(self) -> ComposeResult:
        """Create child widgets for the configuration screen."""
        yield Header()
        with Container(classes="screen-container"):
            yield Static("OpenStack-Ansible Inventory Manager", classes="title")
            yield Static(id="status_message", classes="status-message")
            with HorizontalGroup():
                yield DataTable(id="hosts_table", cursor_type="row", zebra_stripes=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Add Host", id="add_host_button", variant="primary")
                yield Button("Add Group", id="create_group_button", variant="default")
                yield Button.warning("Edit Host", id="edit_host_button")
                yield Button("Save Changes", id="save_inventory_button", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the table and load initial data."""
        self.query_one("#edit_host_button", Button).display = False
        table = self.query_one(DataTable)
        table.add_columns("Hostname", "IP Address", "Management IP", "Groups")
        self.load_configs()

    @work(thread=True)
    def load_configs(self) -> None:
        """Parses YAML files to build the host and group data structures."""
        hosts = {}
        groups = set()
        config_files = self._get_config_files()

        for file_path in config_files:
            try:
                with open(file_path, 'r') as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue

                for key, value in data.items():
                    if key.endswith("_hosts") and isinstance(value, dict):
                        group_name = key[:-6]
                        groups.add(group_name)
                        for hostname, host_details in value.items():
                            if hostname not in hosts:
                                hosts[hostname] = {"ip": "", "management_ip": None, "groups": {}}
                            hosts[hostname]["ip"] = host_details.get("ip")
                            # Only update management_ip if it's explicitly defined to avoid overwriting with None
                            if host_details.get("management_ip"):
                                hosts[hostname]["management_ip"] = host_details["management_ip"]
                            hosts[hostname]["groups"][group_name] = str(file_path)

            except (yaml.YAMLError, IOError) as e:
                self.log(f"Error processing {file_path}: {e}")

        self.hosts_data = hosts
        self.all_groups = groups
        self.initial_hosts_data = copy.deepcopy(hosts)
        self.call_after_refresh(self.update_datatable)

    def update_datatable(self) -> None:
        """Populates the DataTable with the loaded host data."""
        table = self.query_one(DataTable)
        table.clear()
        for hostname, data in sorted(self.hosts_data.items()):
            groups_str = ", ".join(sorted(data["groups"].keys()))
            table.add_row(
                hostname,
                data.get("ip", "N/A"),
                data.get("management_ip") or "N/A",
                groups_str,
                key=hostname
            )

    def watch_hosts_data(self, new_hosts_data: dict) -> None:
        """When host data changes, update the table."""
        if self.is_mounted:
            self.update_datatable()

    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        return self.initial_hosts_data != self.hosts_data

    @on(Button.Pressed, "#edit_host_button")
    def edit_host(self) -> None:
        """Action to edit the selected host."""
        table = self.query_one(DataTable)
        # In modern Textual, cursor_row can be None if no row is selected.
        # We check for that to be safe.
        if table.cursor_row is None:
            return

        hostname = table.get_row_at(table.cursor_row)[0]
        self.action_edit_host(hostname)

    @work
    async def action_add_host(self) -> None:
        """Show the modal for adding a new host."""
        new_host_info = await self.app.push_screen_wait(AddHostScreen(all_groups=list(self.all_groups)))

        if new_host_info:
            hostname = new_host_info["hostname"]
            target_file = str(Path(self.config_path) / "openstack_user_config.yml")

            current_hosts = self.hosts_data.copy()
            current_hosts[hostname] = {
                "ip": new_host_info["ip"],
                "management_ip": new_host_info["management_ip"],
                "groups": {group: target_file for group in new_host_info["groups"]}
            }
            self.hosts_data = current_hosts

    @work
    async def action_create_group(self) -> None:
        """Show the modal for creating a new group."""
        group_info = await self.app.push_screen_wait(CreateGroupScreen(all_hosts=self.hosts_data))

        if group_info:
            group_name = group_info["group_name"]
            selected_hosts = group_info["selected_hosts"]

            # Define the standardized path for the new group file.
            # The file will be created later by action_save_configs.
            conf_d_path = Path(self.config_path) / "conf.d"
            new_group_file = conf_d_path / f"{group_name}.yml"

            # Update reactive properties to refresh the UI
            current_hosts = self.hosts_data.copy()
            for hostname in selected_hosts:
                if hostname in current_hosts:
                    # To trigger the reactive update, we must replace the host's dictionary
                    # with a new one, not modify it in-place.
                    original_host_data = current_hosts[hostname]
                    updated_groups = original_host_data["groups"].copy()
                    updated_groups[group_name] = str(new_group_file)

                    current_hosts[hostname] = {**original_host_data, "groups": updated_groups}

            self.all_groups = self.all_groups.union({group_name})
            self.hosts_data = current_hosts

    @on(DataTable.RowSelected, "#hosts_table")
    def on_host_selected(self, event: DataTable.RowSelected) -> None:
        """Enable the edit button and handle double-clicks."""
        self.query_one("#edit_host_button", Button).display = True

        current_time = time.time()
        # Check for double-click: if the same row is clicked again within 0.5 seconds.
        if (current_time - self._last_row_click_time < 0.5) and (event.row_key == self._last_clicked_row_key):
            table = self.query_one(DataTable)
            hostname = table.get_row_at(event.cursor_row)[0]
            self.action_edit_host(hostname)
            # Reset click time to prevent triple-clicks from re-triggering
            self._last_row_click_time = 0.0
        else:
            self._last_row_click_time = current_time
            self._last_clicked_row_key = event.row_key

    @on(DataTable.HeaderSelected, "#hosts_table")
    def on_no_host_selected(self, event: DataTable.HeaderSelected) -> None:
        """Disable the edit button when selection is cleared."""

        self.query_one("#edit_host_button", Button).display = False

    @work
    async def action_edit_host(self, hostname: str) -> None:
        """Show the modal for editing an existing host."""
        host_to_edit = self.hosts_data.get(hostname)
        if not host_to_edit:
            return

        modal_data = {
            "hostname": hostname,
            "ip": host_to_edit.get("ip"),
            "management_ip": host_to_edit.get("management_ip"),
            "groups": list(host_to_edit.get("groups", {}).keys())
        }

        updated_host_info = await self.app.push_screen_wait(
            AddHostScreen(all_groups=list(self.all_groups), host_data=modal_data)
        )

        if updated_host_info:
            # Update the reactive hosts_data dictionary
            current_hosts = self.hosts_data.copy()

            # Preserve original file paths for existing groups
            original_groups = current_hosts[hostname]["groups"]
            updated_groups = {}
            for group in updated_host_info["groups"]:
                if group in original_groups:
                    updated_groups[group] = original_groups[group]
                else:
                    # Default new group assignments to openstack_user_config.yml
                    updated_groups[group] = str(Path(self.config_path) / "openstack_user_config.yml")

            # Replace the old host dictionary with a new one to trigger the reactive update.
            current_hosts[hostname] = {
                "ip": updated_host_info["ip"],
                "management_ip": updated_host_info["management_ip"],
                "groups": updated_groups,
            }
            self.hosts_data = current_hosts

    @on(Button.Pressed, "#save_inventory_button")
    @work(thread=True)
    def action_save_configs(self) -> None:
        """Saves changes by rewriting modified groups to standardized files."""
        self.query_one("#status_message", Static).update("Saving changes...")

        # Determine which groups have changed
        initial_groups_membership = {}
        for hostname, data in self.initial_hosts_data.items():
            for group in data['groups']:
                initial_groups_membership.setdefault(group, set()).add(hostname)

        current_groups_membership = {}
        for hostname, data in self.hosts_data.items():
            for group in data['groups']:
                current_groups_membership.setdefault(group, set()).add(hostname)

        modified_group_names = set()
        all_group_names = set(initial_groups_membership.keys()) | set(current_groups_membership.keys())

        for group_name in all_group_names:
            initial_members = initial_groups_membership.get(group_name, set())
            current_members = current_groups_membership.get(group_name, set())

            # First, check for changes in group membership
            if initial_members != current_members:
                modified_group_names.add(group_name)
                continue  # Group is modified, no need for deeper checks

            # If membership is identical, check for IP changes on member hosts
            for hostname in current_members:
                initial_host_data = self.initial_hosts_data.get(hostname, {})
                current_host_data = self.hosts_data.get(hostname, {})

                if ((initial_host_data.get('ip') != current_host_data.get('ip')) or (
                        initial_host_data.get('management_ip') != current_host_data.get('management_ip'))):
                    modified_group_names.add(group_name)
                    break  # Found a change, so the group is modified. Move to the next group.

        if not modified_group_names:
            self.query_one("#status_message", Static).update("No changes to save.")
            self.app.bell()
            return

        # For each modified group, find its original file(s) and mark for removal
        files_to_modify = {}
        for group_name in modified_group_names:
            for hostname, host_data in self.initial_hosts_data.items():
                if group_name in host_data['groups']:
                    original_file = host_data['groups'][group_name]
                    files_to_modify.setdefault(original_file, set()).add(group_name)

        # Remove old group definitions, preserving file structure
        yaml_parser = YAML()
        yaml_parser.preserve_quotes = True
        yaml_parser.explicit_start = True
        for file_path_str, groups_to_remove in files_to_modify.items():
            file_path = Path(file_path_str)
            if not file_path.exists():
                continue
            try:
                with file_path.open('r') as f:
                    content = yaml_parser.load(f)
                if not content:
                    continue

                for group_name in groups_to_remove:
                    content.pop(f"{group_name}_hosts", None)

                if not content:
                    file_path.unlink()
                    self.log(f"Deleted empty config file: {file_path}")
                else:
                    with file_path.open('w') as f:
                        yaml_parser.dump(content, f)
                    self.log(f"Updated config file (removed groups): {file_path}")
            except YAMLError as e:
                error_message = f"YAML Error processing {file_path} for save: {e}"
                if "Duplicate merge keys" in str(e):
                    error_message = (
                        f"[red]Error saving {file_path.name}:[/red]\n\n"
                        "Legacy YAML syntax with duplicate '<<' merge keys is not supported for modification.\n"
                        "Please update the file manually to use the modern list syntax, for example:\n\n"
                        r"  <<: \[*anchor1, *anchor2]"
                    )
                self.query_one("#status_message", Static).update(error_message)
                self.app.bell()
                self.log(error_message)
                return
            except IOError as e:
                error_message = f"IO Error processing {file_path} for save: {e}"
                self.query_one("#status_message", Static).update(error_message)
                self.log(error_message)
                return

        # Write new standardized files for all modified groups
        conf_d_path = Path(self.config_path) / "conf.d"
        try:
            conf_d_path.mkdir(exist_ok=True)
        except FileNotFoundError:
            error_message = f"Parent folder {conf_d_path} does not exist. Ensure you have initialized OSA_CONFIG_DIR"
            self.query_one("#status_message", Static).update(error_message)
            self.log(error_message)
            return

        for group_name in modified_group_names:
            new_group_file = conf_d_path / f"{group_name}.yml"
            new_group_data = {f"{group_name}_hosts": {}}
            for hostname in current_groups_membership.get(group_name, set()):
                if hostname in self.hosts_data:
                    host_details = self.hosts_data[hostname]
                    host_entry = {"ip": host_details.get("ip")}
                    if host_details.get("management_ip"):
                        host_entry["management_ip"] = host_details["management_ip"]
                    new_group_data[f"{group_name}_hosts"][hostname] = host_entry
            with new_group_file.open('w') as f:
                yaml_parser.dump(new_group_data, f)

        self.query_one("#status_message", Static).update("[green]Changes saved successfully.[/green]")
        self.load_configs()  # Reload to resync the state, including initial_hosts_data

    @on(Button.Pressed, "#add_host_button")
    def on_add_host_button_pressed(self) -> None:
        """Handle add host button press."""
        self.action_add_host()

    @on(Button.Pressed, "#create_group_button")
    def on_create_group_button_pressed(self) -> None:
        """Handle create group button press."""
        self.action_create_group()
