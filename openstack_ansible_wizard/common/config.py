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


def _get_legacy_files_for_service(config_path: str, service_name: str) -> list[Path]:
    """Returns a list of legacy configuration files for a given service."""
    group_vars_path = Path(config_path) / "group_vars"
    if service_name == "all":
        service_dir_path = group_vars_path / "all"
        if service_dir_path.is_dir():
            return [f for f in service_dir_path.glob("*.y*ml") if f.name not in ("wizard.yml", "wizard.yaml")]
        return []
    else:
        # Legacy files can be in the parent group_vars directory...
        legacy_files = [
            group_vars_path / f"{service_name}.yml",
            group_vars_path / f"{service_name}.yaml",
            group_vars_path / f"{service_name}_all.yml",
            group_vars_path / f"{service_name}_all.yaml",
        ]
        # ...or inside the service-specific directory (excluding the wizard file itself).
        service_dir_path = group_vars_path / service_name
        if service_dir_path.is_dir():
            legacy_files.extend(
                f for f in service_dir_path.glob("*.y*ml") if f.name not in ("wizard.yml", "wizard.yaml")
            )
        return legacy_files


def _migrate_conflicting_group_vars(config_path: str, service_name: str) -> None:
    """Checks for and migrates conflicting Ansible group_vars files.

    According to Ansible's variable precedence, if a directory group_vars/haproxy/
    exists, the file group_vars/haproxy.yml will be ignored. This function detects
    this condition and moves the file into the directory to ensure its variables
    are loaded by Ansible.
    """
    if service_name == "all":
        return

    group_vars_path = Path(config_path) / "group_vars"
    service_dir_path = group_vars_path / service_name
    conflicting_file_yml = group_vars_path / f"{service_name}.yml"
    conflicting_file_yaml = group_vars_path / f"{service_name}.yaml"

    if service_dir_path.is_dir():
        for file_path in [conflicting_file_yml, conflicting_file_yaml]:
            if file_path.is_file():
                new_path = service_dir_path / f"{file_path.stem}_vars{file_path.suffix}"
                file_path.rename(new_path)


def load_service_config(config_path: str, service_name: str) -> tuple[dict, str | None]:
    """Loads and merges configuration for a specific service from multiple YAML files.

    Args:
        config_path: The base path to the openstack_deploy directory.
        service_name: The name of the service (e.g., 'haproxy').

    Returns:
        A tuple containing the merged configuration dictionary and an error message string if any.
    """
    # First, handle potential Ansible variable precedence conflicts.
    _migrate_conflicting_group_vars(config_path, service_name)

    group_vars_path = Path(config_path) / "group_vars"
    service_dir_path = group_vars_path / service_name

    yaml_loader = YAML()
    managed_keys = _get_managed_keys_for_service(service_name)
    final_legacy_managed_config = {}

    legacy_files = _get_legacy_files_for_service(config_path, service_name)
    for legacy_file in legacy_files:
        if legacy_file.exists():
            try:
                with legacy_file.open('r') as f:
                    data = yaml_loader.load(f) or {}

                for key, value in data.items():
                    if key in managed_keys:
                        # We only care about managed keys from legacy files.
                        # Unmanaged keys will be ignored and left in their original files.
                        final_legacy_managed_config[key] = value

            except (YAMLError, IOError, OSError) as e:
                return {}, f"Error migrating legacy file {legacy_file.name}: {e}"

    # Load all YAML files from the service-specific directory.
    # The loading order is alphabetical, which is generally fine.
    merged_config = {}
    yaml_loader = YAML()
    if service_dir_path.is_dir():
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
    # Ensure the target directory exists before performing any write operations.
    save_path = Path(config_path) / "group_vars" / service_name / "wizard.yml"
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # First, handle the migration of any legacy files.
    # This ensures that when we save the new wizard.yml, we also clean up
    # the old files to prevent settings from being defined in two places.
    yaml_loader = YAML()
    yaml_writer = YAML()
    yaml_writer.indent(mapping=2, sequence=4, offset=2)
    yaml_writer.explicit_start = True
    managed_keys = _get_managed_keys_for_service(service_name)

    legacy_files = _get_legacy_files_for_service(config_path, service_name)

    for legacy_file in legacy_files:
        if legacy_file.exists():
            try:
                with legacy_file.open('r') as f:
                    legacy_data = yaml_loader.load(f) or {}

                unmanaged_data = {}
                has_managed_keys = False
                for key, value in legacy_data.items():
                    if key in managed_keys:
                        has_managed_keys = True
                    else:
                        unmanaged_data[key] = value

                # Only modify the file if it contained keys that are now managed by the wizard.
                if has_managed_keys:
                    if unmanaged_data:
                        # Rewrite the file with only the unmanaged data.
                        with legacy_file.open('w') as f:
                            yaml_writer.dump(unmanaged_data, f)
                    else:
                        # If the file only contained managed keys, it's now empty and can be removed.
                        legacy_file.unlink()

            except (IOError, OSError, YAMLError) as e:
                # Re-raise as an exception that the calling screen can catch and display.
                raise IOError(f"Error migrating legacy file {legacy_file.name}: {e}") from e

    # Use the same writer instance to maintain formatting.
    yaml_writer.explicit_start = True
    with save_path.open('w') as f:
        yaml_writer.dump(data, f)
