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

import argparse

from textual.app import App

from openstack_ansible_wizard.screens.initial import InitialCheckScreen


class OpenStackAnsibleWizard(App):
    """The main Textual application for OpenStack-Ansible deployment."""

    CSS_PATH = "css/openstack_ansible_ui.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "toggle_theme", "dark/light")
    ]

    def action_toggle_theme(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark"
            if self.theme == "textual-light"
            else "textual-light"
        )

    def action_quit(self) -> None:
        """Quits the application."""
        self.app.exit()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.push_screen(InitialCheckScreen())


def serve_app(args):
    try:
        from textual_serve.server import Server
    except ImportError:
        raise SystemExit(
            'Required dependencies are missing to serve as a web application! '
            'Please, make sure that OpenStack-Ansible Wizard is installed with '
            '`serve` extras.\n'
            'Try running: `pip install openstack-ansible-wizard[serve]`'
        )

    server = Server(
        command=args.prog, title="OpenStack-Ansible Wizard",
        host=args.host, port=args.port, public_url=args.url
    )
    server.serve()


def run_app(args):
    app = OpenStackAnsibleWizard()
    app.run()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Startup arguments for OpenStack-Ansible Wizard. "
                    "Launch without arguments for the console TUI",
        prog="openstack-ansible-wizard",
    )
    parser.set_defaults(func=run_app)

    subparsers = parser.add_subparsers(dest='subparser_command', help='subcommand help')
    serve_parser = subparsers.add_parser(
        "serve",
        help="Run OpenStack-Ansible Wizard as a web application"
    )
    serve_parser.add_argument(
        "-H", "--host",
        help="IP address or FQDN to run the application on",
        default="localhost"
    )
    serve_parser.add_argument(
        "-p", "--port",
        help="Port to run the application on",
        default=8080, type=int
    )
    serve_parser.add_argument(
        "-u", "--url",
        help="The public URL, if the server is behind a proxy",
    )
    serve_parser.set_defaults(func=serve_app)

    return parser


def main():
    parser = parse_args()
    args = parser.parse_args()
    args.prog = parser.prog
    args.func(args)
