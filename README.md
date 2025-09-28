# OpenStack-Ansible Wizard TUI

<img src="img/logo.png" alt="drawing" width="350"/><br>

A user-friendly Textual-based configuration manager for OpenStack-Ansible.



## Features

-   **Interactive TUI**: A modern terminal interface for managing your OpenStack-Ansible deployment, from initial setup to detailed configuration.
-   **Guided Setup**: Automatically checks for your OpenStack-Ansible repository and configuration directories, guiding you through the first steps.
-   **Automated Bootstrapping**:
    -   Fetches available OpenStack releases and corresponding OpenStack-Ansible versions directly from OpenDev.
    -   Clones the exact version of the OpenStack-Ansible repository you need.
    -   Runs the `bootstrap-ansible.sh` script and displays live log output.
-   **Inventory Management**:
    -   Visually manage your inventory hosts and groups in an interactive table.
    -   Easily add, edit, and assign hosts to groups through intuitive forms.
    -   Saves changes back to your configuration files, automatically organizing groups into standardized files under `conf.d/`.
-   **Network Configuration**: A dedicated interface for managing your OpenStack-Ansible network settings.
-   **Built-in Configuration Editor**:
    -   A powerful side-by-side file browser and YAML editor for direct manipulation of all configuration files.
    -   Supports creating, deleting, and editing files and directories within your configuration path.

## Installation

The application is designed to be run from a cloned repository.

1.  **Prerequisites**

    Ensure you have `git` and Python 3.10+ installed.

2.  **Clone the Repository**

    ```bash
    git clone https://github.com/adriacloud/openstack-ansible-wizard.git
    cd openstack-ansible-wizard
    ```

3.  **Create a Virtual Environment** (Recommended)

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

4.  **Install the Package**

    Install the application and its dependencies using `pip`.

    ```bash
    pip install .
    ```

## Usage

Once installed, you can run the application using the console script created during installation:

```bash
openstack-ansible-wizard
```

### Environment Variables

The application uses the following environment variables to determine default paths. You can set them to point to your existing setup before running the app.

-   `OSA_CLONE_DIR`: The path to your `openstack-ansible` repository. (Default: `/opt/openstack-ansible`)
-   `OSA_CONFIG_DIR`: The path to your OpenStack-Ansible configuration directory. (Default: `/etc/openstack_deploy`)

**Example:**
```bash
export OSA_CONFIG_DIR=~/openstack-configs
openstack-ansible-wizard
```

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.
