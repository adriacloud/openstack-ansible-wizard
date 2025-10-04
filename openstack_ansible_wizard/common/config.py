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
import shutil
from ruamel.yaml import YAML, YAMLError


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
        legacy_files = [group_vars_path / "all.yml", group_vars_path / "all.yaml"]
        new_name = "vars.yml"
    else:
        # Migrate legacy customer config files if they exist
        legacy_files = [
            group_vars_path / f"{service_name}.yml",
            group_vars_path / f"{service_name}.yaml",
            group_vars_path / f"{service_name}_all.yml",
            group_vars_path / f"{service_name}_all.yaml",
        ]
        new_name = None

    for legacy_file in legacy_files:
        if legacy_file.exists():
            try:
                # Move and rename to avoid being picked up by Ansible in the old location
                if not new_name:
                    new_name = f"migrated_{legacy_file.name}"
                shutil.move(str(legacy_file), str(service_dir_path / new_name))
            except (IOError, OSError) as e:
                return {}, f"Error moving legacy file {legacy_file.name}: {e}"

    # Load all YAML files from the service-specific directory.
    # The loading order is alphabetical, which is generally fine.
    merged_config = {}
    yaml = YAML()
    config_files = list(service_dir_path.glob("*.yml")) + list(service_dir_path.glob("*.yaml"))
    # Ensure wizard.yml is loaded last to have the highest precedence
    config_files.sort(key=lambda p: p.name == "wizzard.yml")
    for file in sorted(service_dir_path.glob("*.y*ml")):
        if file.exists():
            try:
                with file.open('r') as f:
                    data = yaml.load(f) or {}
                    merged_config.update(data)
            except (YAMLError, IOError) as e:
                return {}, f"Error loading {file.name}: {e}"

    return merged_config, None


def save_service_config(config_path: str, service_name: str, data: dict) -> None:
    """Saves configuration data to the wizard-specific YAML file."""
    save_path = Path(config_path) / "group_vars" / service_name / "wizzard.yml"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    with save_path.open('w') as f:
        yaml.dump(data, f)
