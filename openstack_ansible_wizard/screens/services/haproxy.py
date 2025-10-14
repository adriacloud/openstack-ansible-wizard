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
import ipaddress
from pathlib import Path
from ruamel.yaml import YAMLError
import time
import yaml

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Grid, VerticalScroll, VerticalGroup, HorizontalGroup
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (Button, Checkbox, DataTable, Footer, Header, Input, Label, Select,
                             Static)
from openstack_ansible_wizard.common.config import load_service_config, save_service_config
from openstack_ansible_wizard.common.screens import WizardConfigScreen


class AddEditBindingScreen(ModalScreen):
    """A modal screen to add or edit an HAProxy binding."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(
        self,
        all_bindings: list[dict],
        binding_data: dict | None = None,
        is_in_lxc: bool = False,
        keepalived_cidrs: dict[str, str] | None = None,
        name: str | None = None, id: str | None = None, classes: str | None = None
    ):
        super().__init__(name, id, classes)
        self.all_bindings = all_bindings
        self.binding_data = binding_data or {}
        self.is_in_lxc = is_in_lxc
        self.keepalived_cidrs = keepalived_cidrs or {}
        self.available_types = self._get_available_types()

    def _get_available_types(self) -> list[str]:
        """Determine which binding types can be selected."""
        all_types = {"internal", "external"}
        used_types = {b.get("type") for b in self.all_bindings if b.get("type")}
        current_type = self.binding_data.get("type")
        if current_type:
            used_types.discard(current_type)
        return sorted(list(all_types - used_types))

    def compose(self) -> ComposeResult:
        is_editing = bool(self.binding_data)
        title = "Edit Binding" if is_editing else "Add Binding"
        button_label = "Update" if is_editing else "Add"

        with Grid(id="haproxy_bind_dialog", classes="modal-screen-grid"):
            yield Static(title, classes="title")
            yield Static(id="haproxy_bind_error", classes="status-message modal-status-message-2")
            yield Label("Type:")
            yield Select(
                options=[(t, t) for t in self.available_types],
                value=self.binding_data.get("type", Select.BLANK),
                id="binding_type",
            )
            yield Label("Address:")
            yield Input(
                value=self.binding_data.get("address", ""), placeholder="e.g. 172.29.236.101", id="binding_address")
            yield Label("Interface:")
            yield Input(
                value=self.binding_data.get("interface", ""), placeholder="e.g. br-mgmt", id="binding_interface")
            with Grid(classes="modal-button-row"):
                yield Button(button_label, variant="primary", id="save_binding")
                yield Button("Cancel", id="cancel_binding")

    @on(Select.Changed, "#binding_type")
    def on_type_changed(self, event: Select.Changed) -> None:
        """Set default values based on the selected binding type."""
        address_input = self.query_one("#binding_address", Input)
        interface_input = self.query_one("#binding_interface", Input)

        # Only set defaults if the fields are currently empty
        if not address_input.value:
            if self.is_in_lxc:
                address_input.value = "*"
            elif self.keepalived_cidrs.get(event.value):
                try:
                    # Use the IP part of the CIDR
                    address_input.value = str(
                        ipaddress.ip_network(self.keepalived_cidrs[event.value], strict=False).network_address
                    )
                except ValueError:
                    pass  # Ignore invalid CIDR

        if not interface_input.value and self.is_in_lxc:
            interface_input.value = "eth1" if event.value == "internal" else "eth20"

    @on(Button.Pressed, "#save_binding")
    def on_save(self) -> None:
        error_widget = self.query_one("#haproxy_bind_error", Static)
        address = self.query_one("#binding_address", Input).value.strip()
        binding_type = self.query_one("#binding_type", Select).value

        if address != "*" and address != "::":
            if "/" in address:
                error_widget.update("[red]Address should not contain a subnet mask.[/red]")
                return
            try:
                ipaddress.ip_address(address)
            except ValueError:
                error_widget.update(f"[red]'{address}' is not a valid IPv4 or IPv6 address.[/red]")
                return

        error_widget.update("")

        result = {
            "type": binding_type,
            "address": address,
            "interface": self.query_one("#binding_interface", Input).value,
        }
        self.dismiss(result)

    @on(Button.Pressed, "#cancel_binding")
    def action_pop_screen(self) -> None:
        self.dismiss(None)


class HAProxyConfigScreen(WizardConfigScreen):
    """A modal screen for configuring HAProxy and Keepalived."""

    SERVICE_NAME = "haproxy"
    config_data = reactive(dict)
    bindings = reactive(list)

    def __init__(
        self, config_path: str,
        name: str | None = None, id: str | None = None, classes: str | None = None
    ):
        super().__init__(name, id, classes)
        self.config_path = config_path
        self.initial_data = {}
        self.selected_binding_key: str | None = None
        # For handling double-clicks on the bindings table
        self._last_row_click_time = 0.0
        self._last_clicked_row_key = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(classes="screen-container"):
            yield Static("HAProxy/Keepalived Configuration", classes="title")
            yield Static(id="haproxy_status_message", classes="status-message")

            with Container(id="main_config_container"):
                with Grid(classes="service-column"):
                    with VerticalScroll():
                        yield HorizontalGroup(
                            Checkbox("Run in LXC container", id="haproxy_in_lxc",
                                     tooltip="Ensure you have configured corresponding Provider Network "
                                             "bridge/interface and that it is assigned to the `haproxy` "
                                             "group.\n"
                                             "This interface also needs to have a default route defined."),
                            Checkbox("Enable SSL for all VIPs", id="haproxy_ssl_all_vips"),
                            classes="service-row",
                        )

                        with VerticalGroup(classes="service-row"):
                            yield HorizontalGroup(
                                Label("HAProxy Bindings:", classes="service-label"),
                                DataTable(id="haproxy_bindings_table", cursor_type="row", zebra_stripes=True),
                            )
                            yield HorizontalGroup(
                                Button("Add Binding", id="add_binding", variant="primary"),
                                Button("Edit Binding", id="edit_binding", variant="default"),
                                Button("Delete Binding", id="delete_binding", variant="error"),
                                classes="button-row"
                            )

                    with VerticalScroll():
                        yield HorizontalGroup(
                            Checkbox("Enable Keepalived", id="keepalived_enabled"),
                            classes="service-row",
                        )
                        with Container(id="keepalived_options"):
                            yield HorizontalGroup(
                                Label("Keepalived External VIP CIDR:", classes="service-label"),
                                Input(
                                    id="haproxy_keepalived_external_vip_cidr",
                                    placeholder="e.g., 192.168.1.100/32",
                                    tooltip="Defined External Endpoint should resolve to this VIP"
                                ),
                                classes="service-row",
                            )
                            yield HorizontalGroup(
                                Label("Keepalived Internal VIP CIDR:", classes="service-label"),
                                Input(
                                    id="haproxy_keepalived_internal_vip_cidr",
                                    placeholder="e.g., 172.29.236.100/32",
                                    tooltip="Defined Internal Endpoint should resolve to this VIP"),
                                classes="service-row",
                            )
                yield Button("Save Changes", id="save_button", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#haproxy_bindings_table", DataTable)
        table.add_columns("Type", "Address", "Interface")
        self.query_one("#delete_binding", Button).display = False
        self.query_one("#edit_binding", Button).display = False
        self.query_one("#main_config_container").display = False
        self.query_one("#haproxy_status_message").update("Loading configuration...")
        self.load_configs()

    @work(thread=True)
    def load_configs(self) -> None:
        data, error = load_service_config(self.config_path, self.SERVICE_NAME)
        if error:
            self.query_one("#haproxy_status_message").update(f"[red]{error}[/red]")
            return

        self.initial_data = copy.deepcopy(data)
        self.config_data = data
        self.bindings = data.get("haproxy_vip_binds", [])
        self.call_after_refresh(self.update_widgets)

    def update_widgets(self) -> None:
        """Populate widgets with loaded data."""
        keepalived_enabled = self.config_data.get("haproxy_use_keepalived", True)

        self.query_one("#keepalived_enabled", Checkbox).value = keepalived_enabled
        self.query_one("#haproxy_in_lxc", Checkbox).value = self.config_data.get("haproxy_in_lxc", False)
        self.query_one("#haproxy_ssl_all_vips", Checkbox).value = self.config_data.get("haproxy_ssl_all_vips", False)

        ext_cidr = self.config_data.get("haproxy_keepalived_external_vip_cidr", "")
        int_cidr = self.config_data.get("haproxy_keepalived_internal_vip_cidr", "")
        self.query_one("#haproxy_keepalived_external_vip_cidr", Input).value = ext_cidr
        self.query_one("#haproxy_keepalived_internal_vip_cidr", Input).value = int_cidr
        self.query_one("#keepalived_options").display = keepalived_enabled

        self.update_bindings_table()

        # Clear loading message and show the main content
        status_widget = self.query_one("#haproxy_status_message")
        if status_widget.render().plain == "Loading configuration...":
            status_widget.update("")

        self.query_one("#main_config_container").display = True

    def update_bindings_table(self) -> None:
        """Refreshes only the bindings table and related buttons."""
        table = self.query_one("#haproxy_bindings_table", DataTable)
        table.clear()
        for i, binding in enumerate(self.bindings):
            table.add_row(
                binding.get("type", "N/A"),
                binding.get("address", "N/A"),
                binding.get("interface", "N/A"),
                key=str(i)
            )
        used_types = {b.get("type") for b in self.bindings}
        self.query_one("#add_binding", Button).display = len(used_types) < 2

    def watch_bindings(self, _: list) -> None:
        if self.is_mounted:
            self.update_bindings_table()

    @on(Checkbox.Changed, "#keepalived_enabled")
    def on_keepalived_toggled(self, event: Checkbox.Changed) -> None:
        self.query_one("#keepalived_options").display = event.value

    @on(DataTable.RowSelected, "#haproxy_bindings_table")
    def on_binding_selected(self, event: DataTable.RowSelected) -> None:
        self.query_one("#delete_binding", Button).display = True
        self.query_one("#edit_binding", Button).display = True
        self.selected_binding_key = event.row_key.value

        current_time = time.time()
        # Check for double-click: if the same row is clicked again within 0.5 seconds.
        if (current_time - self._last_row_click_time < 0.5) and (event.row_key == self._last_clicked_row_key):
            self.on_edit_binding_pressed()
            # Reset click time to prevent triple-clicks from re-triggering
            self._last_row_click_time = 0.0
        else:
            self._last_row_click_time = current_time
            self._last_clicked_row_key = event.row_key

    @on(DataTable.HeaderSelected, "#haproxy_bindings_table")
    def on_binding_deselected(self) -> None:
        self.query_one("#delete_binding", Button).display = False
        self.query_one("#edit_binding", Button).display = False
        self.selected_binding_key = None

    @work
    async def on_add_binding_pressed(self) -> None:
        """Show the modal for adding a new binding."""
        is_in_lxc = self.query_one("#haproxy_in_lxc", Checkbox).value
        keepalived_cidrs = {}
        if self.query_one("#keepalived_enabled", Checkbox).value:
            keepalived_cidrs["external"] = self.query_one("#haproxy_keepalived_external_vip_cidr", Input).value
            keepalived_cidrs["internal"] = self.query_one("#haproxy_keepalived_internal_vip_cidr", Input).value

        new_binding = await self.app.push_screen_wait(
            AddEditBindingScreen(
                all_bindings=self.bindings, is_in_lxc=is_in_lxc,
                keepalived_cidrs=keepalived_cidrs
            )
        )
        if new_binding:
            self.bindings = self.bindings + [new_binding]

    @on(Button.Pressed, "#add_binding")
    def add_binding(self) -> None:
        self.on_add_binding_pressed()

    @work
    async def on_edit_binding_pressed(self) -> None:
        """Show the modal for editing an existing binding."""
        if self.selected_binding_key is None:
            return

        index = int(self.selected_binding_key)
        binding_to_edit = self.bindings[index]

        updated_binding = await self.app.push_screen_wait(
            AddEditBindingScreen(
                all_bindings=self.bindings, binding_data=binding_to_edit
            )
        )

        if updated_binding:
            current_bindings = self.bindings.copy()
            current_bindings[index] = updated_binding
            self.bindings = current_bindings

    @on(Button.Pressed, "#edit_binding")
    def edit_binding(self) -> None:
        self.on_edit_binding_pressed()

    @on(Button.Pressed, "#delete_binding")
    def delete_binding(self) -> None:
        if self.selected_binding_key is not None:
            index = int(self.selected_binding_key)
            new_bindings = self.bindings.copy()
            new_bindings.pop(index)
            self.bindings = new_bindings
            self.on_binding_deselected()

    @work(thread=True)
    @on(Button.Pressed, "#save_button")
    def action_save_configs(self) -> None:
        """Saves all changes back to the user config file."""
        status_widget = self.query_one("#haproxy_status_message", Static)
        status_widget.update("Saving...")

        # Gather data from widgets
        new_config = {
            "haproxy_ssl_all_vips": self.query_one("#haproxy_ssl_all_vips", Checkbox).value,
            "haproxy_vip_binds": self.bindings,
            "haproxy_in_lxc": self.query_one("#haproxy_in_lxc", Checkbox).value,
        }

        if self.query_one("#keepalived_enabled", Checkbox).value:
            ext_cidr = self.query_one("#haproxy_keepalived_external_vip_cidr", Input).value
            int_cidr = self.query_one("#haproxy_keepalived_internal_vip_cidr", Input).value

            # Validate CIDRs
            try:
                if ext_cidr:
                    ipaddress.ip_network(ext_cidr, strict=False)
                if int_cidr:
                    ipaddress.ip_network(int_cidr, strict=False)
            except ValueError as e:
                status_widget.update(f"[red]Invalid CIDR: {e}[/red]")
                return

            new_config["haproxy_keepalived_external_vip_cidr"] = ext_cidr
            new_config["haproxy_keepalived_internal_vip_cidr"] = int_cidr
            new_config["haproxy_use_keepalived"] = True

        else:
            new_config["haproxy_use_keepalived"] = False

        lxc_config, error = self._get_haproxy_lxc_config(new_config["haproxy_in_lxc"])
        if error:
            status_widget.update(error)
            return
        new_config.update(lxc_config)

        # If not in LXC, ensure the key is completely removed before saving.
        if not new_config["haproxy_in_lxc"]:
            if "lxc_container_networks" in new_config:
                del new_config["lxc_container_networks"]

        try:
            # The new function handles directory creation and saving
            save_service_config(self.config_path, self.SERVICE_NAME, new_config)
            status_widget.update("[green]Changes saved successfully.[/green]")
            self.load_configs()
        except (YAMLError, IOError) as e:
            status_widget.update(f"[red]Error saving file: {e}[/red]")

    def _get_haproxy_lxc_config(self, is_in_lxc: bool) -> tuple[dict, str | None]:
        """Manages configs related to running HAProxy in an LXC container.

        - Manages the creation/deletion of `env.d/haproxy.yml`.
        - Generates the `lxc_container_networks` dictionary.

        Returns:
            A tuple containing the generated configuration dictionary and an
            error message string if any.
        """
        env_d_path = Path(self.config_path) / "env.d"
        haproxy_env_file = env_d_path / "haproxy.yml"
        generated_config = {}

        if is_in_lxc:
            try:
                # 1. Manage env.d/haproxy.yml
                env_d_path.mkdir(exist_ok=True)
                env_content = {
                    "container_skel": {
                        "haproxy_container": {
                            "properties": {"is_metal": False}
                        }
                    }
                }
                with haproxy_env_file.open('w') as f:
                    yaml.dump(env_content, f, indent=2, explicit_start=True)

                # 2. Define the static lxc_container_networks config
                lxc_networks = {
                    "lxcbr0_address": {
                        "bridge": "{{ lxc_net_bridge | default('lxcbr0') }}",
                        "bridge_type": "{{ lxc_net_bridge_type | default('linuxbridge') }}",
                        "interface": "eth0",
                        "type": "veth",
                        "dhcp_use_routes": False,
                    }
                }
                generated_config["lxc_container_networks"] = lxc_networks

            except (IOError, yaml.YAMLError, FileNotFoundError) as e:
                return {}, f"[red]Error processing LXC config: {e}[/red]"
        else:
            if haproxy_env_file.exists():
                haproxy_env_file.unlink()

        return generated_config, None

    def _get_current_config(self) -> dict:
        """Gathers current configuration from widgets."""
        current_config = {
            "haproxy_in_lxc": self.query_one("#haproxy_in_lxc", Checkbox).value,
            "haproxy_ssl_all_vips": self.query_one("#haproxy_ssl_all_vips", Checkbox).value,
            "haproxy_vip_binds": self.bindings,
        }

        if self.query_one("#keepalived_enabled", Checkbox).value:
            current_config["haproxy_keepalived_external_vip_cidr"] = self.query_one(
                "#haproxy_keepalived_external_vip_cidr", Input).value
            current_config["haproxy_keepalived_internal_vip_cidr"] = self.query_one(
                "#haproxy_keepalived_internal_vip_cidr", Input).value
            current_config["haproxy_use_keepalived"] = True
        else:
            current_config["haproxy_use_keepalived"] = False

        return current_config

    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        if not self.initial_data:
            return False

        current_config = self._get_current_config()
        initial_config = copy.deepcopy(self.initial_data)

        # We only care about keys that the UI can change.
        for key in current_config:
            if current_config.get(key) != initial_config.get(key):
                return True
        return False

    @classmethod
    def get_managed_keys(cls) -> set[str]:
        """Returns a set of configuration keys managed by this screen."""
        return {
            "haproxy_ssl_all_vips",
            "haproxy_vip_binds",
            "haproxy_in_lxc",
            "haproxy_use_keepalived",
            "haproxy_keepalived_external_vip_cidr",
            "haproxy_keepalived_internal_vip_cidr",
            "lxc_container_networks",
        }
