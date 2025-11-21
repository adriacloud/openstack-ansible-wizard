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

import unittest
from unittest.mock import MagicMock, patch, AsyncMock, call

from openstack_ansible_wizard.screens.bootstrap import CloneOSAScreen, BootstrapOsaSreen
from textual.widgets import Select, Button, Static, Log


class TestCloneOSAScreen(unittest.TestCase):
    def setUp(self):
        self.screen = CloneOSAScreen(clone_path="/opt/openstack-ansible")
        self.screen._app = MagicMock()

        # Mock widgets
        self.clone_dest_static = MagicMock(spec=Static)
        self.repo_check_static = MagicMock(spec=Static)
        self.os_version_select = MagicMock(spec=Select)
        self.osa_version_select = MagicMock(spec=Select)
        self.clone_button = MagicMock(spec=Button)

        self.widget_map = {
            "#clone_destination": self.clone_dest_static,
            "#repository_check": self.repo_check_static,
            "#openstack-version": self.os_version_select,
            "#openstack-ansible-version": self.osa_version_select,
            "#clone_repo": self.clone_button,
        }

        self.screen.query_one = MagicMock(side_effect=lambda x, y=None: self.widget_map.get(x))
        self.screen.add_class = MagicMock()
        self.screen.remove_class = MagicMock()

    @patch("openstack_ansible_wizard.screens.bootstrap.Path")
    @patch("openstack_ansible_wizard.screens.bootstrap.utils.path_writable")
    def test_check_path_is_clone_destination_valid(self, mock_writable, mock_path):
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj

        # Path does not exist, but is writable
        mock_path_obj.exists.return_value = False
        mock_writable.return_value = True

        result = self.screen.check_path_is_clone_destination()

        self.assertTrue(result)
        self.assertIn("can be used", self.screen.clone_destination_text)
        self.assertIn("green", self.screen.clone_destination_text)

    @patch("openstack_ansible_wizard.screens.bootstrap.Path")
    def test_check_path_is_clone_destination_exists_invalid(self, mock_path):
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj

        mock_path_obj.exists.return_value = True
        # Mock generate.py check

        def path_side_effect(arg):
            if str(arg).endswith("generate.py"):
                m = MagicMock()
                m.exists.return_value = False
                return m
            return mock_path_obj
        mock_path.side_effect = path_side_effect

        result = self.screen.check_path_is_clone_destination()

        self.assertFalse(result)
        self.assertIn("already exist", self.screen.clone_destination_text)

    @patch("openstack_ansible_wizard.screens.bootstrap.Path")
    @patch("openstack_ansible_wizard.screens.bootstrap.utils.path_writable")
    def test_check_path_is_clone_destination_not_writable(self, mock_writable, mock_path):
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.exists.return_value = False
        mock_writable.return_value = False

        result = self.screen.check_path_is_clone_destination()

        self.assertFalse(result)
        self.assertIn("not writtable", self.screen.clone_destination_text)

    @patch("openstack_ansible_wizard.screens.bootstrap.Path")
    def test_check_path_is_osa_dir_valid(self, mock_path):
        mock_path_obj = MagicMock()

        def path_side_effect(arg):
            if str(arg).endswith("generate.py"):
                m = MagicMock()
                m.is_file.return_value = True
                return m
            return mock_path_obj

        mock_path.side_effect = path_side_effect
        mock_path_obj.exists.return_value = True

        result = self.screen.check_path_is_osa_dir()

        self.assertTrue(result)
        self.assertIn("valid OpenStack-Ansible directory", self.screen.clone_destination_text)

    @patch("openstack_ansible_wizard.screens.bootstrap.utils.get_openstack_series")
    def test_fetch_openstack_releases_success(self, mock_get_series):
        mock_get_series.return_value = [
            {'release-id': '2024.1', 'name': 'Caracal'},
            {'release-id': '2023.2', 'name': 'Bobcat'}
        ]

        self.screen.fetch_openstack_releases.__wrapped__(self.screen)

        self.os_version_select.set_options.assert_called()
        self.assertFalse(self.os_version_select.disabled)
        self.screen.remove_class.assert_called_with('no-version-fetch')

    @patch("openstack_ansible_wizard.screens.bootstrap.utils.get_openstack_series")
    def test_fetch_openstack_releases_empty(self, mock_get_series):
        mock_get_series.return_value = []

        self.screen.fetch_openstack_releases.__wrapped__(self.screen)

        self.assertIn("Failed to fetch", self.screen.repository_check_text)

    @patch("openstack_ansible_wizard.screens.bootstrap.utils.get_osa_versions")
    def test_fetch_osa_releases_success(self, mock_get_versions):
        mock_get_versions.return_value = ['29.0.0', '29.0.1']
        event = MagicMock()
        event.value = "Caracal"

        self.screen.fetch_osa_releases.__wrapped__(self.screen, event)

        self.osa_version_select.set_options.assert_called()
        self.assertFalse(self.osa_version_select.disabled)
        self.screen.remove_class.assert_called_with('no-version-selected')

    def test_enable_clone_button(self):
        event = MagicMock()
        event.value = "29.0.0"

        # Mock check_path_is_clone_destination to return True
        with patch.object(self.screen, 'check_path_is_clone_destination', return_value=True):
            self.screen.enable_clone_button(event)

            self.assertFalse(self.clone_button.disabled)
            self.assertEqual(self.screen.clone_version, "29.0.0")


class TestCloneOSAScreenAsync(unittest.IsolatedAsyncioTestCase):
    @patch("openstack_ansible_wizard.screens.bootstrap.GitCloneScreen")
    async def test_action_clone_repo(self, MockGitCloneScreen):
        mock_screen = MagicMock(spec=CloneOSAScreen)
        mock_screen.app.push_screen_wait = AsyncMock()
        mock_screen.clone_path = "/opt/osa"
        mock_screen.clone_version = "29.0.0"

        await CloneOSAScreen.action_clone_repo(mock_screen)

        mock_screen.app.push_screen_wait.assert_called_once()

    @patch("openstack_ansible_wizard.screens.bootstrap.BootstrapOsaSreen")
    async def test_action_bootstrap_osa(self, MockBootstrapScreen):
        mock_screen = MagicMock(spec=CloneOSAScreen)
        mock_screen.app.push_screen_wait = AsyncMock()
        mock_screen.clone_path = "/opt/osa"

        await CloneOSAScreen.action_bootstrap_osa(mock_screen)

        mock_screen.app.push_screen_wait.assert_called_once()

    @patch("openstack_ansible_wizard.screens.bootstrap.PathInputScreen")
    async def test_action_change_path(self, MockPathInputScreen):
        mock_screen = MagicMock(spec=CloneOSAScreen)
        mock_screen.app.push_screen_wait = AsyncMock(return_value="/new/path")

        await CloneOSAScreen.action_change_path.__wrapped__(mock_screen)

        mock_screen.app.push_screen_wait.assert_called_once()
        self.assertEqual(mock_screen.clone_path, "/new/path")
        mock_screen.check_clone.assert_called_once()


class TestBootstrapOsaScreenAsync(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch("openstack_ansible_wizard.common.git.get_git_version", return_value="29.0.0"):
            self.screen = BootstrapOsaSreen(path="/opt/osa")
        self.screen._app = MagicMock()

        self.log_widget = MagicMock(spec=Log)
        self.status_static = MagicMock(spec=Static)

        self.widget_map = {
            "#osa-bootstrap-progress": self.log_widget,
            "#osa-bootstrap-status-message": self.status_static,
        }

        self.screen.query_one = MagicMock(side_effect=lambda x, y=None: self.widget_map.get(x))
        self.screen.add_class = MagicMock()
        self.screen.remove_class = MagicMock()

    @patch("asyncio.create_subprocess_shell")
    async def test_action_bootstrap_success(self, mock_subprocess):
        # Mock subprocess
        mock_proc = MagicMock()
        mock_proc.stdout = AsyncMock()
        # Mock async iterator for stdout
        mock_proc.stdout.__aiter__.return_value = [b"line1\n", b"line2\n"]
        mock_proc.wait = AsyncMock(return_value=0)

        mock_subprocess.return_value = mock_proc

        # We need to use the real instance but bypass @work
        # However, @work wraps the method.
        # We can call __wrapped__ on the instance method.
        await self.screen.action_bootstrap.__wrapped__(self.screen)

        mock_subprocess.assert_called_once()
        self.log_widget.write_line.assert_has_calls([call("line1"), call("line2")])
        self.assertIn("successfully", self.screen.status_message)
        self.screen.add_class.assert_any_call("bootstrap-completed")

    @patch("asyncio.create_subprocess_shell")
    async def test_action_bootstrap_failure(self, mock_subprocess):
        mock_proc = MagicMock()
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.__aiter__.return_value = [b"error\n"]
        mock_proc.wait = AsyncMock(return_value=1)

        mock_subprocess.return_value = mock_proc

        await self.screen.action_bootstrap.__wrapped__(self.screen)

        self.assertIn("failed", self.screen.status_message)

    @patch("asyncio.create_subprocess_shell")
    async def test_action_bootstrap_exception(self, mock_subprocess):
        mock_subprocess.side_effect = Exception("Boom")

        await self.screen.action_bootstrap.__wrapped__(self.screen)

        self.assertIn("Error running bootstrap", self.screen.status_message)


if __name__ == '__main__':
    unittest.main()
