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

from textual import on, work
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Grid, HorizontalGroup, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Static

from openstack_ansible_wizard.common.config import load_service_config, save_service_config
from openstack_ansible_wizard.common.screens import WizardConfigScreen


class PKIConfigScreen(ModalScreen):
    """A modal screen to configure PKI settings."""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, pki_data: dict | None = None, name: str | None = None,
                 id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.pki_data = pki_data or {}

    def compose(self) -> ComposeResult:
        with Grid(id="pki_dialog", classes="modal-screen-grid"):
            yield Static("PKI Configuration", classes="title")
            yield Label("Generate Root CA:")
            yield Checkbox(
                id="generate_root_ca",
                value=self.pki_data.get("generate_root_ca", True),
                tooltip="You may unselect this box, if you need to generate new "
                        "intermediate certificate.\n"
                        "This assumes, that Root CA with respective name is already "
                        "present on the filesystem in pki/roots."
            )
            yield Label("CA Name:")
            yield Input(id="pki_name", placeholder="e.g., ExampleCorp", value=self.pki_data.get("name", ""))
            yield Label("Common Name (CN):", classes="pki-root-fields")
            yield Input(id="pki_cn", placeholder="e.g., Example Corp Root CA",
                        value=self.pki_data.get("cn", ""), classes="pki-root-fields")
            yield Label("Alternate CA Name:")
            yield Input(id="pki_alt_name", placeholder="e.g., ExampleCorpIntermediate",
                        value=self.pki_data.get("alt_name", ""))
            yield Label("Alternate CA Common Name (CN):")
            yield Input(id="pki_alt_cn", placeholder="e.g., Example Corp Intermediate CA",
                        value=self.pki_data.get("alt_cn", ""))
            yield Label("Email:")
            yield Input(id="pki_email", placeholder="e.g., ca@example.com", value=self.pki_data.get("email", ""))
            yield Label("Country (C):")
            yield Input(id="pki_country", placeholder="e.g., GB", value=self.pki_data.get("country", ""))
            yield Label("State (ST):")
            yield Input(id="pki_state", placeholder="e.g., England", value=self.pki_data.get("state", ""))
            yield Label("Organization (O):")
            yield Input(id="pki_org", placeholder="e.g., Example Corp", value=self.pki_data.get("org", ""))
            yield Label("Organizational Unit (OU):")
            yield Input(id="pki_unit", placeholder="e.g., IT Security", value=self.pki_data.get("unit", ""))
            with Grid(classes="modal-button-row"):
                yield Button("Update", variant="primary", id="update_pki")
                yield Button("Cancel", id="cancel_pki")

    def on_mount(self) -> None:
        """Set initial visibility of root CA fields."""
        self.toggle_root_fields(self.query_one("#generate_root_ca", Checkbox).value)

    @on(Button.Pressed, "#update_pki")
    def on_save(self) -> None:
        result = {
            "generate_root_ca": self.query_one("#generate_root_ca", Checkbox).value,
            "name": self.query_one("#pki_name", Input).value,
            "cn": self.query_one("#pki_cn", Input).value,
            "email": self.query_one("#pki_email", Input).value,
            "country": self.query_one("#pki_country", Input).value,
            "state": self.query_one("#pki_state", Input).value,
            "org": self.query_one("#pki_org", Input).value,
            "unit": self.query_one("#pki_unit", Input).value,
            "alt_name": self.query_one("#pki_alt_name", Input).value,
            "alt_cn": self.query_one("#pki_alt_cn", Input).value,
        }
        self.dismiss(result)

    @on(Button.Pressed, "#cancel_pki")
    def action_pop_screen(self) -> None:
        self.dismiss(None)

    def toggle_root_fields(self, show: bool) -> None:
        """Toggle the visibility of the root CA configuration fields."""
        for object in self.query(".pki-root-fields"):
            object.display = show

    @on(Checkbox.Changed, "#generate_root_ca")
    def on_generate_root_ca_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes to show/hide root CA fields."""
        self.toggle_root_fields(event.value)


class GenericConfigScreen(WizardConfigScreen):
    """A modal screen for generic configuration flags."""

    SERVICE_NAME = "all"
    config_data = reactive(dict)

    def __init__(self, config_path: str, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.config_path = config_path
        self.initial_data = {}
        self.pki_config_data = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(classes="screen-container"):
            yield Static("Generic Configuration", classes="title")
            yield Static(id="generic_status_message", classes="status-message")

            with Grid(classes="service-column"):
                with VerticalScroll():
                    yield HorizontalGroup(
                        Label("Internal Endpoint:", classes="service-label"),
                        Input(id="internal_lb_vip_address", placeholder="e.g., internal.example.cloud"),
                        classes="service-row",
                    )

                    yield HorizontalGroup(
                        Label("External Endpoint:", classes="service-label"),
                        Input(id="external_lb_vip_address", placeholder="e.g., example.cloud"),
                        classes="service-row",
                    )
                    yield HorizontalGroup(
                        Label("PKI configuration:", classes="service-label"),
                        Button("Manage", id="pki_button", variant="default"),
                        classes="service-row",
                    )

            with HorizontalGroup(classes="button-row-single"):
                yield Button("Save Changes", id="save_button", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#generic_status_message", Static).update("Loading configuration...")
        self.load_configs()

    @work(thread=True)
    def load_configs(self) -> None:
        status_widget = self.query_one("#generic_status_message")
        if status_widget.render().plain != "Loading configuration...":
            status_widget.update("Loading configuration...")

        data, error = load_service_config(self.config_path, self.SERVICE_NAME)
        if error:
            self.query_one("#generic_status_message").update(f"[red]{error}[/red]")
            return

        self.initial_data = copy.deepcopy(data)
        self.config_data = data
        self._populate_pki_data_from_config()
        self.call_after_refresh(self.update_widgets)

    def update_widgets(self) -> None:
        """Populate widgets with loaded data."""
        status_widget = self.query_one("#generic_status_message")
        if status_widget.render().plain == "Loading configuration...":
            status_widget.update("")
        self.query_one("#internal_lb_vip_address", Input).value = self.config_data.get("internal_lb_vip_address", "")
        self.query_one("#external_lb_vip_address", Input).value = self.config_data.get("external_lb_vip_address", "")

    def _populate_pki_data_from_config(self) -> None:
        """Extracts PKI data from loaded config to populate the modal."""
        authorities = self.config_data.get("openstack_pki_authorities", [])
        if not authorities:
            self.pki_config_data = {}
            return

        root_ca = authorities[0]
        # Find the intermediate CA, which is typically the one with a 'signed_by' key.
        intermediate_ca = next((ca for ca in authorities if "signed_by" in ca), None)

        # If no intermediate CA is found but there's a second entry, assume it's the one.
        if not intermediate_ca and len(authorities) > 1:
            intermediate_ca = authorities[1]

        org_name = root_ca.get("organization_name", "")
        self.pki_config_data = {
            "name": root_ca.get("name", ""),
            "cn": root_ca.get("cn", ""),
            "email": root_ca.get("email_address", ""),
            "country": root_ca.get("country_name", ""),
            "state": root_ca.get("state_or_province_name", ""),
            "org": org_name,
            "unit": root_ca.get("organizational_unit_name", ""),
            "alt_name": intermediate_ca.get("name", "") if intermediate_ca else f"{root_ca.get('name', '')}-alt",
            "alt_cn": intermediate_ca.get("cn", "") if intermediate_ca else f"{org_name} Intermediate CA",
            "generate_root_ca": True,
        }

    @work(thread=True)
    @on(Button.Pressed, "#save_button")
    def action_save_configs(self) -> None:
        """Saves all changes back to the user config file."""
        status_widget = self.query_one("#generic_status_message", Static)
        status_widget.update("Saving...")

        new_config = {
            "internal_lb_vip_address": self.query_one("#internal_lb_vip_address", Input).value,
            "external_lb_vip_address": self.query_one("#external_lb_vip_address", Input).value,
        }

        if self.pki_config_data:
            pki = self.pki_config_data
            ca_name = pki.get("name")
            if ca_name:
                # Use the alternate name from the form, or generate a default.
                alt_name = pki.get("alt_name") or f"{ca_name}-alt"
                authorities = []

                root_ca = {
                    "name": ca_name,
                    "provider": "selfsigned",
                    "basic_constraints": "CA:TRUE",
                    "cn": pki.get("cn"),
                    "email_address": pki.get("email"),
                    "country_name": pki.get("country"),
                    "state_or_province_name": pki.get("state"),
                    "organization_name": pki.get("org"),
                    "organizational_unit_name": pki.get("unit"),
                    "key_usage": ["digitalSignature", "cRLSign", "keyCertSign"],
                    "not_after": "+3650d",
                }

                intermediate_ca = {
                    "name": alt_name,
                    "provider": "ownca",
                    "basic_constraints": "CA:TRUE,pathlen:0",
                    "cn": pki.get("alt_cn") or f"{pki.get('org')} Intermediate CA",
                    "email_address": pki.get("email"),
                    "country_name": pki.get("country"),
                    "state_or_province_name": pki.get("state"),
                    "organization_name": pki.get("org"),
                    "organizational_unit_name": "Intermediate CA",
                    "key_usage": ["digitalSignature", "cRLSign", "keyCertSign"],
                    "not_after": "+3650d",
                    "signed_by": ca_name,
                }

                if pki.get("generate_root_ca"):
                    authorities.append(root_ca)
                authorities.append(intermediate_ca)

                new_config["openstack_pki_authorities"] = authorities
                new_config["openstack_pki_install_ca"] = [ca_name] if pki.get("generate_root_ca") else []
                new_config["openstack_pki_service_intermediate_cert_name"] = alt_name

        try:
            save_service_config(self.config_path, self.SERVICE_NAME, new_config)
            status_widget.update("[green]Changes saved successfully.[/green]")
            # Update initial_data to reflect the new saved state
            self.initial_data = self._get_current_config()
        except Exception as e:
            status_widget.update(f"[red]Error saving file: {e}[/red]")

    @work
    @on(Button.Pressed, "#pki_button")
    async def configure_pki_settings(self) -> None:
        """Show the modal for configuring PKI."""
        updated_pki_data = await self.app.push_screen_wait(
            PKIConfigScreen(pki_data=self.pki_config_data)
        )
        if updated_pki_data:
            self.pki_config_data = updated_pki_data

    def _get_current_config(self) -> dict:
        """Gathers current configuration from widgets."""
        current_config = {
            "internal_lb_vip_address": self.query_one("#internal_lb_vip_address", Input).value,
            "external_lb_vip_address": self.query_one("#external_lb_vip_address", Input).value,
        }

        # Reconstruct the PKI part of the config from the modal's data
        if self.pki_config_data:
            pki = self.pki_config_data
            ca_name = pki.get("name")
            if ca_name:
                alt_name = pki.get("alt_name") or f"{ca_name}-alt"
                authorities = []
                root_ca = {
                    "name": ca_name, "provider": "selfsigned", "basic_constraints": "CA:TRUE",
                    "cn": pki.get("cn"), "email_address": pki.get("email"),
                    "country_name": pki.get("country"), "state_or_province_name": pki.get("state"),
                    "organization_name": pki.get("org"), "organizational_unit_name": pki.get("unit"),
                    "key_usage": ["digitalSignature", "cRLSign", "keyCertSign"], "not_after": "+3650d",
                }
                intermediate_ca = {
                    "name": alt_name, "provider": "ownca", "basic_constraints": "CA:TRUE,pathlen:0",
                    "cn": pki.get("alt_cn") or f"{pki.get('org')} Intermediate CA", "email_address": pki.get("email"),
                    "country_name": pki.get("country"), "state_or_province_name": pki.get("state"),
                    "organization_name": pki.get("org"), "organizational_unit_name": "Intermediate CA",
                    "key_usage": ["digitalSignature", "cRLSign", "keyCertSign"], "not_after": "+3650d",
                    "signed_by": ca_name,
                }
                if pki.get("generate_root_ca"):
                    authorities.append(root_ca)
                authorities.append(intermediate_ca)

                current_config["openstack_pki_authorities"] = authorities
                current_config["openstack_pki_install_ca"] = [ca_name] if pki.get("generate_root_ca") else []
                current_config["openstack_pki_service_intermediate_cert_name"] = alt_name

        return current_config

    def has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        if not self.initial_data:
            return False

        # Get the full current state from the UI
        current_state = self._get_current_config()

        # Compare only the keys managed by this screen
        managed_keys = self.get_managed_keys()
        for key in managed_keys:
            # Use .get() with a default to handle cases where a key might not exist in one dictionary
            if current_state.get(key) != self.initial_data.get(key):
                return True

        return False

    @classmethod
    def get_managed_keys(cls) -> set[str]:
        """Returns a set of configuration keys managed by this screen."""
        return {"internal_lb_vip_address", "external_lb_vip_address", "openstack_pki_authorities",
                "openstack_pki_install_ca", "openstack_pki_service_intermediate_cert_name"}
