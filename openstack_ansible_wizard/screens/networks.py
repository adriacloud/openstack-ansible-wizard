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
import time
import yaml

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Grid, HorizontalGroup
from textual.widgets import Header, Footer, Static, Button, DataTable, Input, Label, Select, TextArea, Checkbox
from textual.reactive import reactive
from textual.screen import ModalScreen
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap
from textual import on, work

from openstack_ansible_wizard.common.screens import ConfirmExitScreen, WizardConfigScreen


class AddEditStaticRouteScreen(ModalScreen):
    """A modal screen to add or edit a static route."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(
            self, provider_network_options: list[str],
            route_data: dict | None = None,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.provider_network_options = provider_network_options
        self.route_data = route_data or {}

    def compose(self) -> ComposeResult:
        is_editing = bool(self.route_data)
        title = "Edit Static Route" if is_editing else "Add Static Route"
        button_label = "Update Route" if is_editing else "Add Route"

        with Grid(id="static_route_dialog", classes="modal-screen-grid"):
            yield Static(title, classes="title")
            yield Static(id="static_route_error", classes="status-message modal-status-message-2")
            yield Label("Provider Network:")
            yield Select(
                options=[(name, name) for name in self.provider_network_options],
                value=self.route_data.get("network_bridge", Select.BLANK),
                id="route_network_bridge",
                allow_blank=False,
                disabled=is_editing  # Can't change the parent network when editing
            )
            yield Label("CIDR:")
            yield Input(value=self.route_data.get("cidr", ""), id="route_cidr", placeholder="0.0.0.0/0")
            yield Label("Gateway:")
            yield Input(value=self.route_data.get("gateway", ""), id="route_gateway", placeholder="192.168.1.1")

            with Grid(classes="modal-button-row"):
                yield Button(button_label, variant="primary", id="add_static_route", classes="confirm-button")
                yield Button("Cancel", id="cancel_button", classes="confirm-button")

    @on(Button.Pressed, "#add_static_route")
    def on_save(self) -> None:
        error_widget = self.query_one("#static_route_error", Static)
        network_bridge = self.query_one("#route_network_bridge", Select).value
        cidr = self.query_one("#route_cidr", Input).value.strip()
        gateway = self.query_one("#route_gateway", Input).value.strip()

        if not all([network_bridge, cidr, gateway]):
            error_widget.update("[red]All fields are required.[/red]")
            return

        # Validate CIDR
        try:
            ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            error_widget.update(f"[red]'{cidr}' is not a valid network CIDR.[/red]")
            self.app.bell()
            return

        # Validate Gateway
        try:
            ipaddress.ip_address(gateway)
        except ValueError:
            error_widget.update(f"[red]'{gateway}' is not a valid Gateway IP address.[/red]")
            self.app.bell()
            return

        result = {
            "network_bridge": network_bridge,
            "cidr": cidr,
            "gateway": gateway,
        }
        self.dismiss(result)

    @on(Button.Pressed, "#cancel_button")
    def action_pop_screen(self) -> None:
        self.dismiss(None)


class AddEditProviderNetworkScreen(ModalScreen):
    """A modal screen to add or edit a provider network."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(
            self, cidr_options: list[str], existing_interfaces: list[str], is_management_network_set: bool,
            network_data: dict | None = None,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.cidr_options = cidr_options
        self.existing_interfaces = existing_interfaces
        self.network_data = network_data or {}
        self.is_management_network_set = is_management_network_set

    def compose(self) -> ComposeResult:
        is_editing = bool(self.network_data)
        title = "Edit Provider Network" if is_editing else "Add Provider Network"
        button_label = "Update Network" if is_editing else "Add Network"
        net = self.network_data.get('network', {})

        is_current_management = net.get("is_management_address", False)
        management_checkbox_disabled = self.is_management_network_set and not is_current_management
        management_checkbox_tooltip = "Only one network can be defined as management."
        if management_checkbox_disabled:
            management_checkbox_tooltip += "\nPlease unselect current active management network first."

        # Validate that the network's currently assigned CIDR still exists.
        # If not, reset it to blank to prevent a crash when rendering the Select widget.
        current_ip_from_q = net.get("ip_from_q", Select.BLANK)
        if current_ip_from_q not in self.cidr_options:
            current_ip_from_q = Select.BLANK

        with Grid(id="provider_network_dialog", classes="modal-screen-grid"):
            yield Static(title, classes="title")
            yield Static(id="provider_network_error", classes="status-message modal-status-message-2")
            yield Label("Bridge:")
            yield Input(value=net.get("container_bridge", ""), id="net_bridge", placeholder="br-mgmt")
            yield Label("Type:")
            yield Select(
                options=[(t, t) for t in ['raw', 'vxlan', 'geneve', 'flat', 'vlan']],
                value=net.get("type", Select.BLANK),
                id="net_type",
            )
            yield Label("Container Interface:")
            yield Input(value=net.get("container_interface", ""), id="net_interface", placeholder="eth1")
            yield Label("Host Interface (optional):")
            yield Input(value=net.get("host_bind_override", ""), id="host_interface", placeholder="bond1")
            yield Label("IP From Network:")
            yield Select(
                options=[(name, name) for name in self.cidr_options],
                value=current_ip_from_q,
                id="net_ip_from_q",
                allow_blank=True
            )
            yield Label("Groups:")
            yield TextArea(text="\n".join(net.get("group_binds", [])), id="net_groups",
                           placeholder="e.g., all_containers",
                           tooltip="Groups to which the network should be attached.\n\n"
                                   "Provide one group per line.")
            yield Label("Is Management:")
            yield Checkbox(
                "", value=is_current_management, id="is_management_checkbox",
                disabled=management_checkbox_disabled,
                tooltip=management_checkbox_tooltip
            )
            with Grid(classes="modal-button-row"):
                yield Button(button_label, variant="primary", id="add_provider_network", classes="confirm-button")
                yield Button("Cancel", id="cancel_button", classes="confirm-button")

    @on(Button.Pressed, "#add_provider_network")
    def on_save(self) -> None:
        error_widget = self.query_one("#provider_network_error", Static)

        bridge = self.query_one("#net_bridge", Input).value.strip()
        net_type = self.query_one("#net_type", Select).value
        interface = self.query_one("#net_interface", Input).value.strip()
        ip_from_q = self.query_one("#net_ip_from_q", Select).value

        errors = []
        if not bridge:
            errors.append("Bridge")
        if not net_type:
            errors.append("Type")
        if not interface:
            errors.append("Container Interface")
        if not ip_from_q or ip_from_q is Select.BLANK:
            errors.append("IP From Network")

        if errors:
            error_widget.update(f"[red]Required fields cannot be empty:\n{', '.join(errors)}.[/red]")
            return

        if interface in self.existing_interfaces:
            error_widget.update(f"[red]Container Interface '{interface}' is already in use.[/red]")
            return

        # Start with a copy of the original data to preserve un-edited fields.
        result = copy.deepcopy(self.network_data)
        if "network" not in result:
            result["network"] = {}

        groups_text = self.query_one("#net_groups", TextArea).text
        groups = [g.strip() for g in groups_text.splitlines() if g.strip()]

        # Update only the fields managed by the UI
        result["network"]["container_bridge"] = bridge
        result["network"]["type"] = net_type
        result["network"]["container_interface"] = interface
        result["network"]["ip_from_q"] = ip_from_q
        result["network"]["group_binds"] = groups

        host_bind_override = self.query_one("#host_interface", Input).value.strip() or None
        if host_bind_override or self.network_data.get("network", {}).get("host_bind_override"):
            result["network"]["host_bind_override"] = host_bind_override

        is_management = self.query_one("#is_management_checkbox", Checkbox).value
        if is_management:
            result["network"]["is_management_address"] = True
        elif "is_management_address" in result["network"]:
            del result["network"]["is_management_address"]

        self.dismiss(result)

    @on(Button.Pressed, "#cancel_button")
    def action_pop_screen(self) -> None:
        self.dismiss(None)


class AddEditCidrNetworkScreen(ModalScreen):
    """A modal screen to add or edit a CIDR network."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(
            self, cidr_data: tuple[str, dict] | None = None,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.cidr_data = cidr_data

    def compose(self) -> ComposeResult:
        is_editing = self.cidr_data is not None
        if is_editing:
            cidr_name, data = self.cidr_data
            cidr_value = data.get("cidr", "")
            used_ips_text = "\n".join(data.get("used_ips", []))
            button_label = "Update CIDR"
        else:
            cidr_name, cidr_value, used_ips_text = "", "", ""
            button_label = "Add CIDR"

        title = "Edit CIDR Network" if is_editing else "Add CIDR Network"

        with Grid(id="cidr_network_dialog", classes="modal-screen-grid"):
            yield Static(title, classes="title")
            yield Static(id="cidr_error_message", classes="status-message modal-status-message-2")
            yield Label("Network Name:")
            yield Input(value=cidr_name, placeholder="management",
                        tooltip="Human-readable name of the network", id="cidr_name")
            yield Label("CIDR Value:")
            yield Input(value=cidr_value, placeholder="e.g., 192.168.1.0/24", id="cidr_value")
            yield Label("Used IPs:")
            yield TextArea(
                text=used_ips_text, id="cidr_used_ips",
                placeholder="e.g., 192.168.1.50,192.168.1.200",
                tooltip="Define IP ranges which are reserved and should NOT be used inside of LXC containers.\n\n"
                        "One range per line"
            )
            with Grid(classes="modal-button-row"):
                yield Button(button_label, variant="primary", id="add_cidr_button", classes="confirm-button")
                yield Button("Cancel", id="cancel_button", classes="confirm-button")

    @on(Button.Pressed, "#add_cidr_button")
    def on_save(self) -> None:
        error_widget = self.query_one("#cidr_error_message", Static)
        name = self.query_one("#cidr_name", Input).value.strip()
        value = self.query_one("#cidr_value", Input).value.strip()
        used_ips = self.query_one("#cidr_used_ips", TextArea).text.splitlines()
        used_ips_list = [line.strip() for line in used_ips if line.strip()]

        if not name or not value:
            error_widget.update("[red]Network Name and CIDR Value cannot be empty.[/red]")
            return

        # 1. Validate the CIDR value itself
        if "/" not in value:
            error_widget.update("[red]CIDR value must include a netmask (e.g., /24).[/red]")
            return

        try:
            network = ipaddress.ip_network(value, strict=False)
        except ValueError:
            error_widget.update(f"[red]'{value}' is not a valid network CIDR.[/red]")
            return

        # 2. Validate that all used IPs are valid and within the CIDR
        try:
            for ip_range in used_ips_list:
                parts = [p.strip() for p in ip_range.split(',')]
                start_ip = ipaddress.ip_address(parts[0])
                end_ip = ipaddress.ip_address(parts[-1])
                if start_ip not in network or end_ip not in network:
                    error_widget.update(f"[red]IP range '{ip_range}' is outside the '{value}' CIDR.[/red]")
                    return
        except ValueError as e:
            error_widget.update(f"[red]Invalid IP address in 'Used IPs': {e}[/red]")
            return

        result = {
            "cidr": value,
            "used_ips": used_ips_list
        }
        self.dismiss((name, result))

    @on(Button.Pressed, "#cancel_button")
    def action_pop_screen(self) -> None:
        self.dismiss(None)


class NetworkScreen(WizardConfigScreen):
    """A screen for managing OpenStack-Ansible network configurations."""

    provider_networks = reactive(list)
    cidr_networks = reactive(dict)
    static_routes = reactive(list)

    def __init__(
            self, config_path: str, osa_path: str,
            name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.config_path = config_path
        self.user_config_file = Path(self.config_path) / "openstack_user_config.yml"
        self.osa_path = osa_path
        self.initial_data = {}
        # For handling double-clicks on the CIDR table
        self._last_cidr_row_click_time = 0.0
        self._last_clicked_cidr_row_key = None
        self.selected_cidr_key: str | None = None
        # For handling double-clicks on the Provider Network table
        self._last_pn_row_click_time = 0.0
        self._last_clicked_pn_row_key = None
        self.selected_pn_key: str | None = None
        # For handling double-clicks on the Static Route table
        self._last_sr_row_click_time = 0.0
        self._last_clicked_sr_row_key = None
        self.selected_sr_key: str | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()
        with ScrollableContainer(classes="screen-container"):
            yield Static("Network Configuration", classes="title")
            yield Static(id="status_message", classes="status-message")

            yield Static("Provider Networks", classes="subtitle")
            yield DataTable(id="provider_networks_table", cursor_type="row", zebra_stripes=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Add Network", id="add_provider_net_button", variant="primary")
                yield Button("Edit Network", id="edit_provider_net_button", variant="default", disabled=True)
                yield Button("Delete Network", id="delete_provider_net_button", variant="error", disabled=True)

            yield Static("CIDR Networks & Used IPs", classes="subtitle")
            yield DataTable(id="cidr_networks_table", cursor_type="row", zebra_stripes=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Add CIDR", id="add_cidr_button", variant="primary")
                yield Button("Edit CIDR", id="edit_cidr_button", variant="default", disabled=True)
                yield Button("Delete CIDR", id="delete_cidr_button", variant="error", disabled=True)

            yield Static("Static Routes", classes="subtitle")
            yield DataTable(id="static_routes_table", cursor_type="row", zebra_stripes=True)
            with HorizontalGroup(classes="button-row"):
                yield Button("Add Route", id="add_static_route_button", variant="primary")
                yield Button("Edit Route", id="edit_static_route_button", variant="default", disabled=True)
                yield Button("Delete Route", id="delete_static_route_button", variant="error", disabled=True)

            with HorizontalGroup(classes="button-row-single"):
                yield Button("Save Changes", id="save_button", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the tables and load initial data."""
        self.query_one("#edit_provider_net_button", Button).display = False
        self.query_one("#delete_provider_net_button", Button).display = False
        self.query_one("#edit_cidr_button", Button).display = False
        self.query_one("#delete_cidr_button", Button).display = False
        self.query_one("#edit_static_route_button", Button).display = False
        self.query_one("#delete_static_route_button", Button).display = False

        pn_table = self.query_one("#provider_networks_table", DataTable)
        pn_table.add_columns("Mgmt", "Bridge", "Type", "Interface", "IP From", "Groups")

        cn_table = self.query_one("#cidr_networks_table", DataTable)
        cn_table.add_columns("Name", "CIDR", "Used IP Ranges")

        sr_table = self.query_one("#static_routes_table", DataTable)
        sr_table.add_columns("Network", "CIDR", "Gateway")

        self.load_configs()

    @work(thread=True)
    def load_configs(self) -> None:
        """Parses openstack_user_config.yml to load and associate network data."""
        if not self.user_config_file.exists():
            self.query_one("#status_message").update(f"[red]File not found: {self.user_config_file}[/red]")
            return

        try:
            with self.user_config_file.open('r') as f:
                data = yaml.safe_load(f)
        except (YAMLError, IOError) as e:
            self.query_one("#status_message").update(f"[red]Error loading YAML: {e}[/red]")
            return

        if data is None:
            data = {}

        self.initial_data = copy.deepcopy(data)

        # Load raw data
        global_overrides = data.get("global_overrides", {})
        provider_networks_raw = global_overrides.get("provider_networks", [])
        cidr_networks_raw = data.get("cidr_networks", {})
        used_ips_raw = data.get("used_ips", [])

        # Process and associate CIDRs with Used IPs
        processed_cidrs = {
            name: {"cidr": value, "used_ips": []}
            for name, value in cidr_networks_raw.items()
        }
        # Create ipaddress objects for efficient checking
        cidr_net_objects = []
        for name, cidr_str in cidr_networks_raw.items():
            try:
                cidr_net_objects.append((name, ipaddress.ip_network(cidr_str, strict=False)))
            except ValueError:
                self.log(f"Warning: Invalid CIDR '{cidr_str}' for network '{name}' found in config.")
                continue

        for ip_range_str in used_ips_raw:
            try:
                # Use the first IP of a range to determine which network it belongs to
                first_ip_str = ip_range_str.split(',')[0].strip()
                ip = ipaddress.ip_address(first_ip_str)
                found = False
                for net_name, network in cidr_net_objects:
                    if ip in network:
                        processed_cidrs[net_name]["used_ips"].append(ip_range_str)
                        found = True
                        break
                if not found:
                    self.log(f"Warning: Used IP range '{ip_range_str}' does not belong to any defined CIDR network.")
            except ValueError:
                self.log(f"Warning: Invalid IP address or range '{ip_range_str}' found in used_ips.")

        # Process static routes
        processed_routes = []
        for i, p_net in enumerate(provider_networks_raw):
            net_info = p_net.get("network", {})
            bridge = net_info.get("container_bridge")
            if bridge and "static_routes" in net_info:
                for route in net_info["static_routes"]:
                    processed_routes.append({
                        "network_bridge": bridge,
                        **route
                    })

        # Set reactive properties
        self.provider_networks = provider_networks_raw
        self.cidr_networks = processed_cidrs
        self.static_routes = processed_routes

        self.call_after_refresh(self.update_tables)

    def update_tables(self) -> None:
        """Populates all DataTables with the loaded data."""
        # Provider Networks
        pn_table = self.query_one("#provider_networks_table", DataTable)
        pn_table.clear()
        for i, item in enumerate(self.provider_networks):
            net = item.get("network", {})
            is_mgmt = "✓" if net.get("is_management_address") else ""
            groups = ", ".join(net.get("group_binds", []))
            pn_table.add_row(
                is_mgmt,
                net.get("container_bridge", "N/A"),
                net.get("type", "N/A"),
                net.get("container_interface", "N/A"),
                net.get("ip_from_q", "N/A"),
                groups,
                key=str(i)
            )

        # CIDR Networks
        cn_table = self.query_one("#cidr_networks_table", DataTable)
        cn_table.clear()
        for name, data in sorted(self.cidr_networks.items()):
            used_ips_str = ", ".join(data.get("used_ips", []))
            cn_table.add_row(name, data.get("cidr", "N/A"), used_ips_str, key=name)

        # Static Routes
        sr_table = self.query_one("#static_routes_table", DataTable)
        sr_table.clear()
        for i, route in enumerate(self.static_routes):
            sr_table.add_row(
                route.get("network_bridge", "N/A"),
                route.get("cidr", "N/A"),
                route.get("gateway", "N/A"),
                key=str(i)
            )

    def watch_cidr_networks(self, _: dict) -> None:
        """When CIDR network data changes, update the table."""
        if self.is_mounted:
            self.update_tables()

    def watch_provider_networks(self, new_provider_networks: list) -> None:
        """When provider network data changes, re-process derived data and update tables."""
        if self.is_mounted:
            # Re-process static routes from the updated provider networks
            processed_routes = []
            for i, p_net in enumerate(new_provider_networks):
                net_info = p_net.get("network", {})
                bridge = net_info.get("container_bridge")
                if bridge and "static_routes" in net_info:
                    for route in net_info["static_routes"]:
                        processed_routes.append({
                            "network_bridge": bridge,
                            **route
                        })
            self.static_routes = processed_routes
            self.update_tables()

    @on(DataTable.RowSelected, "#cidr_networks_table")
    def on_cidr_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle CIDR table row selection to enable buttons and detect double-clicks."""
        edit_cidr_button = self.query_one("#edit_cidr_button", Button)
        edit_cidr_button.disabled = False
        edit_cidr_button.display = True
        delete_cidr_button = self.query_one("#delete_cidr_button", Button)
        delete_cidr_button.disabled = False
        delete_cidr_button.display = True
        self.selected_cidr_key = event.row_key

        current_time = time.time()
        if (current_time - self._last_cidr_row_click_time < 0.5) and (event.row_key == self._last_clicked_cidr_row_key):
            self.action_edit_cidr(self.selected_cidr_key.value)
            self._last_cidr_row_click_time = 0.0  # Reset to prevent triple-click
        else:
            self._last_cidr_row_click_time = current_time
            self._last_clicked_cidr_row_key = event.row_key

    @on(DataTable.HeaderSelected, "#cidr_networks_table")
    def on_cidr_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle clearing selection in the CIDR table."""
        edit_cidr_button = self.query_one("#edit_cidr_button", Button)
        edit_cidr_button.disabled = True
        edit_cidr_button.display = False
        delete_cidr_button = self.query_one("#delete_cidr_button", Button)
        delete_cidr_button.disabled = True
        delete_cidr_button.display = False
        self.selected_cidr_key = None

    @on(DataTable.RowSelected, "#provider_networks_table")
    def on_pn_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Provider Network table row selection."""
        edit_provider_net_button = self.query_one("#edit_provider_net_button", Button)
        edit_provider_net_button.disabled = False
        edit_provider_net_button.display = True
        delete_provider_net_button = self.query_one("#delete_provider_net_button", Button)
        delete_provider_net_button.disabled = False
        delete_provider_net_button.display = True
        self.selected_pn_key = event.row_key.value

        current_time = time.time()
        if (current_time - self._last_pn_row_click_time < 0.5) and (event.row_key == self._last_clicked_pn_row_key):
            self.action_edit_provider_network()
            self._last_pn_row_click_time = 0.0
        else:
            self._last_pn_row_click_time = current_time
            self._last_clicked_pn_row_key = event.row_key

    @on(DataTable.HeaderSelected, "#provider_networks_table")
    def on_pn_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle clearing selection in the Provider Network table."""
        edit_provider_net_button = self.query_one("#edit_provider_net_button", Button)
        edit_provider_net_button.disabled = True
        edit_provider_net_button.display = False
        delete_provider_net_button = self.query_one("#delete_provider_net_button", Button)
        delete_provider_net_button.disabled = True
        delete_provider_net_button.display = False
        self.selected_pn_key = None

    @on(DataTable.RowSelected, "#static_routes_table")
    def on_sr_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Static Route table row selection."""
        edit_button = self.query_one("#edit_static_route_button", Button)
        edit_button.disabled = False
        edit_button.display = True
        delete_button = self.query_one("#delete_static_route_button", Button)
        delete_button.disabled = False
        delete_button.display = True
        self.selected_sr_key = event.row_key.value

        current_time = time.time()
        if (current_time - self._last_sr_row_click_time < 0.5) and (event.row_key == self._last_clicked_sr_row_key):
            self.action_edit_static_route()
            self._last_sr_row_click_time = 0.0
        else:
            self._last_sr_row_click_time = current_time
            self._last_clicked_sr_row_key = event.row_key

    @on(DataTable.HeaderSelected, "#static_routes_table")
    def on_sr_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle clearing selection in the Static Route table."""
        edit_button = self.query_one("#edit_static_route_button", Button)
        edit_button.disabled = True
        edit_button.display = False
        delete_button = self.query_one("#delete_static_route_button", Button)
        delete_button.disabled = True
        delete_button.display = False
        self.selected_sr_key = None

    @on(Button.Pressed, "#add_provider_net_button")
    @work
    async def action_add_provider_network(self) -> None:
        """Show the modal for adding a new provider network."""
        cidr_options = list(self.cidr_networks.keys())
        existing_interfaces = [
            p.get('network', {}).get('container_interface')
            for p in self.provider_networks
            if p.get('network', {}).get('container_interface')
        ]
        is_management_set = any(p.get('network', {}).get('is_management_address') for p in self.provider_networks)
        new_net_info = await self.app.push_screen_wait(AddEditProviderNetworkScreen(
            cidr_options=cidr_options,
            existing_interfaces=existing_interfaces,
            is_management_network_set=is_management_set
        ))

        if new_net_info:
            current_nets = self.provider_networks.copy()
            current_nets.append(new_net_info)
            self.provider_networks = current_nets

    @on(Button.Pressed, "#edit_provider_net_button")
    @work
    async def action_edit_provider_network(self) -> None:
        """Show the modal for editing an existing provider network."""
        if self.selected_pn_key is None:
            return

        index = int(self.selected_pn_key)
        network_to_edit = self.provider_networks[index]
        cidr_options = list(self.cidr_networks.keys())
        existing_interfaces = [
            p.get('network', {}).get('container_interface')
            for i, p in enumerate(self.provider_networks)
            if i != index and p.get('network', {}).get('container_interface')
        ]
        is_management_set_elsewhere = any(
            p.get('network', {}).get('is_management_address')
            for i, p in enumerate(self.provider_networks) if i != index
        )

        updated_net_info = await self.app.push_screen_wait(
            AddEditProviderNetworkScreen(cidr_options=cidr_options, existing_interfaces=existing_interfaces,
                                         network_data=network_to_edit,
                                         is_management_network_set=is_management_set_elsewhere,)
        )
        if updated_net_info:
            current_nets = self.provider_networks.copy()
            current_nets[index] = updated_net_info
            self.provider_networks = current_nets

    @on(Button.Pressed, "#delete_provider_net_button")
    @work
    async def on_delete_provider_network_button_pressed(self) -> None:
        """Delete the selected provider network after confirmation."""
        if self.selected_pn_key is None:
            return

        index = int(self.selected_pn_key)
        net_bridge = self.provider_networks[index].get('network', {}).get('container_bridge', f"at index {index}")
        message = f"Delete provider network '{net_bridge}'?"
        confirmed = await self.app.push_screen_wait(ConfirmExitScreen(message=message))
        if confirmed:
            current_nets = self.provider_networks.copy()
            current_nets.pop(index)
            self.provider_networks = current_nets
            # After deletion, clear the selection state to prevent errors
            edit_provider_net_button = self.query_one("#edit_provider_net_button", Button)
            edit_provider_net_button.disabled = True
            edit_provider_net_button.display = False
            delete_provider_net_button = self.query_one("#delete_provider_net_button", Button)
            delete_provider_net_button.disabled = True
            delete_provider_net_button.display = False
            self.selected_pn_key = None

    @on(Button.Pressed, "#add_cidr_button")
    @work
    async def on_add_cidr_button_pressed(self) -> None:
        """Show the modal for adding a new CIDR network."""
        cidr_info = await self.app.push_screen_wait(AddEditCidrNetworkScreen())
        if cidr_info:
            name, data = cidr_info
            current_cidrs = self.cidr_networks.copy()
            current_cidrs[name] = data
            self.cidr_networks = current_cidrs

    @on(Button.Pressed, "#edit_cidr_button")
    def on_edit_cidr_button_pressed(self) -> None:
        """Handle edit CIDR button press."""
        if self.selected_cidr_key is not None:
            self.action_edit_cidr(self.selected_cidr_key.value)

    @work
    async def action_edit_cidr(self, cidr_name: str) -> None:
        """Show the modal for editing an existing CIDR network."""
        # The cidr_name is now passed directly as an argument.
        if not cidr_name:
            return

        cidr_to_edit = self.cidr_networks.get(cidr_name)
        if not cidr_to_edit:
            return

        updated_cidr_info = await self.app.push_screen_wait(
            AddEditCidrNetworkScreen(cidr_data=(cidr_name, cidr_to_edit))
        )

        if updated_cidr_info:
            name, data = updated_cidr_info
            current_cidrs = self.cidr_networks.copy()
            current_cidrs[name] = data
            self.cidr_networks = current_cidrs

    @on(Button.Pressed, "#delete_cidr_button")
    @work
    async def on_delete_cidr_button_pressed(self) -> None:
        """Delete the selected CIDR network after confirmation."""
        if self.selected_cidr_key is None:
            return

        cidr_name = self.selected_cidr_key.value
        confirmed = await self.app.push_screen_wait(ConfirmExitScreen(f"Delete CIDR network '{cidr_name}'?"))
        if confirmed:
            current_cidrs = self.cidr_networks.copy()
            if current_cidrs.pop(cidr_name, None):
                self.cidr_networks = current_cidrs
                # After deletion, clear the selection state
                edit_cidr_button = self.query_one("#edit_cidr_button", Button)
                edit_cidr_button.disabled = True
                edit_cidr_button.display = False
                delete_cidr_button = self.query_one("#delete_cidr_button", Button)
                delete_cidr_button.disabled = True
                delete_cidr_button.display = False
                self.selected_cidr_key = None

    @on(Button.Pressed, "#add_static_route_button")
    @work
    async def action_add_static_route(self) -> None:
        """Show the modal for adding a new static route."""
        provider_net_options = [
            p.get("network", {}).get("container_bridge")
            for p in self.provider_networks
            if p.get("network", {}).get("container_bridge")
        ]
        if not provider_net_options:
            self.query_one("#status_message").update(
                "[yellow]Cannot add a static route without a provider network.[/yellow]")
            self.app.bell()
            return

        new_route_info = await self.app.push_screen_wait(AddEditStaticRouteScreen(
            provider_network_options=provider_net_options
        ))

        if new_route_info:
            # Find the provider network to add this route to
            current_nets = copy.deepcopy(self.provider_networks)
            for p_net in current_nets:
                if p_net.get("network", {}).get("container_bridge") == new_route_info["network_bridge"]:
                    p_net.setdefault("network", {}).setdefault("static_routes", []).append({
                        "cidr": new_route_info["cidr"],
                        "gateway": new_route_info["gateway"],
                    })
                    # Re-assign to trigger the watcher
                    self.provider_networks = current_nets
                    break

    @on(Button.Pressed, "#edit_static_route_button")
    @work
    async def action_edit_static_route(self) -> None:
        """Show the modal for editing an existing static route."""
        if self.selected_sr_key is None:
            return

        index = int(self.selected_sr_key)
        route_to_edit = self.static_routes[index]

        provider_net_options = [
            p.get("network", {}).get("container_bridge") for p in self.provider_networks
            if p.get("network", {}).get("container_bridge")
        ]

        updated_route_info = await self.app.push_screen_wait(
            AddEditStaticRouteScreen(provider_network_options=provider_net_options, route_data=route_to_edit)
        )

        if updated_route_info:
            # Find the original route in the provider_networks structure and update it
            # The bridge name is constant, so we use it to find the parent network.
            current_nets = copy.deepcopy(self.provider_networks)
            for p_net in current_nets:
                if p_net.get("network", {}).get("container_bridge") == route_to_edit["network_bridge"]:
                    routes = p_net.get("network", {}).get("static_routes", [])
                    routes.remove({"cidr": route_to_edit["cidr"], "gateway": route_to_edit["gateway"]})
                    routes.append({"cidr": updated_route_info["cidr"], "gateway": updated_route_info["gateway"]})
                    self.provider_networks = current_nets
                    return

    @on(Button.Pressed, "#delete_static_route_button")
    @work
    async def on_delete_static_route_button_pressed(self) -> None:
        """Delete the selected static route after confirmation."""
        if self.selected_sr_key is None:
            return

        index = int(self.selected_sr_key)
        route_to_delete = self.static_routes[index]
        message = f"Delete route '{route_to_delete['cidr']}' via '{route_to_delete['gateway']}'?"
        confirmed = await self.app.push_screen_wait(ConfirmExitScreen(message=message))

        if confirmed:
            current_nets = copy.deepcopy(self.provider_networks)
            for p_net in current_nets:
                if p_net.get("network", {}).get("container_bridge") == route_to_delete["network_bridge"]:
                    routes_list = p_net.get("network", {}).get("static_routes", [])
                    routes_list.remove({"cidr": route_to_delete["cidr"], "gateway": route_to_delete["gateway"]})
                    break

            # After deletion, clear the selection state to prevent errors
            edit_button = self.query_one("#edit_static_route_button", Button)
            edit_button.disabled = True
            edit_button.display = False
            delete_button = self.query_one("#delete_static_route_button", Button)
            delete_button.disabled = True
            delete_button.display = False
            self.selected_sr_key = None
            self.provider_networks = current_nets

    @on(Button.Pressed, "#save_button")
    def on_save_button_pressed(self) -> None:
        """Handle save button press by calling the action worker."""
        self.action_save_configs()

    @work(thread=True)
    def action_save_configs(self) -> None:
        """Saves all network changes back to openstack_user_config.yml."""
        status_widget = self.query_one("#status_message", Static)
        status_widget.update("Saving changes...")

        if not self.has_unsaved_changes():
            status_widget.update("No changes to save.")
            self.app.bell()
            return

        # Validate that exactly one management network is set
        management_nets = [
            p for p in self.provider_networks if p.get("network", {}).get("is_management_address")
        ]
        if len(management_nets) != 1:
            status_widget.update(
                "[red]Error: Exactly one provider network must be set as the management network.[/red]")
            self.app.bell()
            return

        yaml_parser = YAML()
        yaml_parser.indent(mapping=2, sequence=4, offset=2)
        yaml_parser.preserve_quotes = True
        yaml_parser.explicit_start = True

        # Reconstruct data from the current UI state
        new_cidrs = {name: data['cidr'] for name, data in self.cidr_networks.items()}
        new_used_ips = []
        for data in self.cidr_networks.values():
            new_used_ips.extend(data['used_ips'])

        # Load the current file content to update it
        try:
            with self.user_config_file.open('r') as f:
                config_data = yaml_parser.load(f) or {}

            config_data['used_ips'] = new_used_ips

            # To ensure YAML anchors are always used, we first make sure both keys
            # point to the same object, then we modify that object in-place.
            global_overrides = config_data.setdefault('global_overrides', {})

            # Ensure cidr_networks is a ruamel.yaml object that supports anchors
            if 'cidr_networks' not in config_data or not hasattr(config_data['cidr_networks'], 'yaml_set_anchor'):
                config_data['cidr_networks'] = CommentedMap()

            config_data['cidr_networks'].yaml_set_anchor('cidr_networks', always_dump=True)
            config_data['cidr_networks'].clear()
            config_data['cidr_networks'].update(new_cidrs)
            global_overrides['cidr_networks'] = config_data['cidr_networks']
            global_overrides['provider_networks'] = self.provider_networks

            with self.user_config_file.open('w') as f:
                yaml_parser.dump(config_data, f)
        except YAMLError as e:
            error_message = str(type(e))
            if "Duplicate merge keys" in str(e) or "DuplicateKeyError" in str(type(e)):
                error_message = (
                    f"[red]Error saving {self.user_config_file}:[/red]\n\n"
                    "Legacy YAML syntax with duplicate '<<' merge keys is not supported for modification.\n"
                    "Please update the file manually to use the modern list syntax, for example:\n\n"
                    r"  <<: \[*anchor1, *anchor2]"
                )
            self.query_one("#status_message", Static).update(error_message)
            self.app.bell()
            self.log(f"YAML Error processing {self.user_config_file} for save: {e}")
            return  # Stop the save process

        except IOError as e:
            error_message = f"IO Error processing {self.user_config_file} for save: {e}"
            self.log(error_message)
            self.query_one("#status_message", Static).update(error_message)
            return

        status_widget.update("[green]Changes saved successfully.[/green]")
        # Reload configs to reset the 'initial_data' state and reflect the saved state
        self.load_configs()

    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        # If the initial data was empty (e.g., new file), any current data is an unsaved change.
        if not self.initial_data:
            return bool(self.provider_networks or self.cidr_networks)

        # Reconstruct the original format from the current state
        current_cidrs = {name: data['cidr'] for name, data in self.cidr_networks.items()}
        current_used_ips = []
        for data in self.cidr_networks.values():
            current_used_ips.extend(data['used_ips'])

        # Create a representation of the current state in the file's format
        current_data = copy.deepcopy(self.initial_data)
        current_data["cidr_networks"] = current_cidrs
        current_data["used_ips"] = sorted(current_used_ips)
        current_data.setdefault("global_overrides", {})["provider_networks"] = self.provider_networks

        # The original data from the file might not be sorted
        initial_comparable_data = copy.deepcopy(self.initial_data)
        if "used_ips" in initial_comparable_data and initial_comparable_data["used_ips"] is not None:
            initial_comparable_data["used_ips"] = sorted(initial_comparable_data["used_ips"])
        else:
            initial_comparable_data["used_ips"] = []

        return initial_comparable_data != current_data
