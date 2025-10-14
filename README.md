# OpenStack-Ansible Wizard TUI

<img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/logo.png" alt="drawing" width="350"/><br>

A user-friendly Textual-based configuration manager for OpenStack-Ansible.



## Features

-   **Interactive TUI**: A modern terminal interface for managing your OpenStack-Ansible deployment, from initial setup to detailed configuration.
-   **Guided Setup**: Automatically checks for your OpenStack-Ansible repository and configuration directories, guiding you through the first steps.
-   **Guided Bootstrapping**:

    <img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/osa-wizard-bootstrap.gif" alt="drawing" width="500"/><br>

    -   Fetches available OpenStack releases and corresponding OpenStack-Ansible versions directly from OpenDev.
    -   Clones the exact version of the OpenStack-Ansible repository you need.
    -   Runs the `bootstrap-ansible.sh` script and displays live log output.
-   **Inventory Management**:

    <img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/osa-wizard-inventory.gif" alt="drawing" width="500"/><br>

    -   Visually manage your inventory hosts and groups in an interactive table.
    -   Easily add, edit, and assign hosts to groups through intuitive forms.
    -   Saves changes back to your configuration files, automatically organizing groups into standardized files under `conf.d/`.
-   **Network Configuration**:

    <img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/osa-wizard-network.gif" alt="drawing" width="500"/><br>

    -   Create, edit and delete CIDR definitions together with used subnets
    -   Manage provider networks definitions
-   **Services Configuration**: Manage most common settings and scenarios in (almost) intuitive way

    <img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/osa-wizard-config.gif" alt="drawing" width="500"/><br>

    -   Configure Public/Private endpoint names
    -   Define details for issued self-signed Certificate Authority
    -   Configure HAProxy and Keepalived details
    -   More to come soon!
-   **Built-in Configuration Editor**:

    <img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/osa-wizard-editor.gif" alt="drawing" width="500"/><br>

    -   A powerful side-by-side file browser and YAML editor for direct manipulation of all configuration files.
    -   Supports creating, deleting, and editing files and directories within your configuration path.
-   **Web TUI Mode**: Serve the entire application as a web-based TUI, accessible from any modern browser.

    <img src="https://raw.githubusercontent.com/adriacloud/openstack-ansible-wizard/main/img/osa-wizard-web-serve.gif" alt="drawing" width="500"/><br>

-   **Can be used with existing deployments**: At your own risk, of course! We are trying our best to have compatibility and do not break existing environments, but this is not always guaranteed.
## Installation


1.  **Create a Python Virtual Environment** (Recommended)

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

4.  **Install the Package**

    Install the application and its dependencies using `pip`.

    ```bash
    # For standard TUI usage
    pip install openstack-ansible-wizard

    # To include web server capabilities
    pip install openstack-ansible-wizard[serve]
    ```

    You can also run the application without installation, which might be
    convenient during development:

    ```bash
    # Install requirements manually
    pip install -r requirements.txt
    # Run application
    python3 run.py
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

### Web TUI Mode

The application can also be served as a web-based TUI that you can access from your browser. This is useful for running the wizard on a remote server.

First, ensure you have installed the application with the `serve` extras (see Installation section).

Then, run the `serve` command:

```
openstack-ansible-wizard serve --host localhost --port 8080
```

You can then access the application by navigating to `http://localhost:8080` in your web browser.

## License

This project is licensed under the Apache License 2.0. See the LICENSE file for details.
