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

import inspect
from pathlib import Path
from ruamel.yaml import YAML, YAMLError

from openstack_ansible_wizard.common.screens import WizardConfigScreen
from openstack_ansible_wizard.screens import services


def _get_managed_keys_for_service(service_name: str) -> set[str]:
    """Dynamically finds the managed keys for a given service by inspecting screen classes."""
    for name, obj in inspect.getmembers(services, inspect.ismodule):
        for _, class_obj in inspect.getmembers(obj, inspect.isclass):
            if issubclass(class_obj, WizardConfigScreen) and hasattr(class_obj, 'SERVICE_NAME') and \
                    class_obj.SERVICE_NAME == service_name:
                return class_obj.get_managed_keys()
    return set()


def load_service_config(config_path: str, service_name: str) -> tuple[dict, str | None]:
    """Loads and merges configuration for a specific service from multiple YAML files.

    Args:
        config_path: The base path to the openstack_deploy directory.
        service_name: The name of the service (e.g., 'haproxy').

    Returns:
        A tuple containing the merged configuration dictionary and an error message string if any.
    """
    group_vars_path = Path(config_path) / "group_vars"
    service_dir_path = group_vars_path / service_name
    service_dir_path.mkdir(exist_ok=True)

    if service_name == "all":
        # For 'all', we treat all non-wizard YAML files in the directory as potential legacy sources.
        legacy_files = [f for f in service_dir_path.glob("*.y*ml") if f.name not in ("wizard.yml", "wizard.yaml")]
    else:
        # Migrate legacy customer config files if they exist
        legacy_files = [
            group_vars_path / f"{service_name}.yml",
            group_vars_path / f"{service_name}.yaml",
            group_vars_path / f"{service_name}_all.yml",
            group_vars_path / f"{service_name}_all.yaml",
        ]

    yaml_loader = YAML()
    yaml_writer = YAML()
    yaml_writer.indent(mapping=2, sequence=4, offset=2)
    yaml_writer.explicit_start = True
    managed_keys = _get_managed_keys_for_service(service_name)
    final_legacy_managed_config = {}

    for legacy_file in legacy_files:
        if legacy_file.exists():
            try:
                with legacy_file.open('r') as f:
                    data = yaml_loader.load(f) or {}

                unmanaged_data = {}
                file_managed_config = {}
                for key, value in data.items():
                    if key in managed_keys:
                        file_managed_config[key] = value
                    else:
                        unmanaged_data[key] = value

                # If there are no managed keys in the file, there's nothing to migrate.
                if not file_managed_config:
                    continue

                if unmanaged_data:
                    # Rewrite the file with only the unmanaged data.
                    with legacy_file.open('w') as f:
                        yaml_writer.dump(unmanaged_data, f)
                else:
                    # If the file only contained managed keys, it's now empty and can be removed.
                    legacy_file.unlink()
                # Add the managed keys from this file to the final collection
                final_legacy_managed_config.update(file_managed_config)
            except (IOError, OSError) as e:
                return {}, f"Error migrating legacy file {legacy_file.name}: {e}"

    # Load all YAML files from the service-specific directory.
    # The loading order is alphabetical, which is generally fine.
    merged_config = {}
    yaml_loader = YAML()
    # Sort files to ensure a consistent merge order, with 'wizard.yml' loaded last.
    config_files = sorted(service_dir_path.glob("*.y*ml"), key=lambda p: (p.name != 'wizard.yml', p.name))
    for file in config_files:
        if file.exists():
            try:
                with file.open() as f:
                    data = yaml_loader.load(f) or {}
                    merged_config.update(data)
            except (YAMLError, IOError) as e:
                return {}, f"Error loading {file.name}: {e}"

    # The final config is the legacy managed values updated with anything loaded
    # from the service directory. This ensures wizard.yml takes precedence,
    # but legacy values are used as defaults if wizard.yml doesn't exist.
    final_config = final_legacy_managed_config.copy()
    final_config.update(merged_config)

    return final_config, None


def save_service_config(config_path: str, service_name: str, data: dict) -> None:
    """Saves configuration data to the wizard-specific YAML file."""
    save_path = Path(config_path) / "group_vars" / service_name / "wizard.yml"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.explicit_start = True
    with save_path.open('w') as f:
        yaml.dump(data, f)
