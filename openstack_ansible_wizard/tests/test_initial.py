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
from unittest.mock import MagicMock, patch, AsyncMock

from openstack_ansible_wizard.screens.initial import InitialCheckScreen
from textual.widgets import Button, Static


class TestInitialCheckScreen(unittest.TestCase):

    def setUp(self):
        self.app = MagicMock()
        self.screen = InitialCheckScreen()
        self.screen._app = self.app

        # Mock query_one to return mocks for widgets
        self.osa_status = MagicMock(spec=Static)
        self.etc_status = MagicMock(spec=Static)
        self.status_message = MagicMock(spec=Static)
        self.clone_button = MagicMock(spec=Button)
        self.custom_osa_button = MagicMock(spec=Button)
        self.proceed_config_button = MagicMock(spec=Button)
        self.proceed_network_button = MagicMock(spec=Button)
        self.proceed_service_button = MagicMock(spec=Button)
        self.init_config_button = MagicMock(spec=Button)
        self.custom_config_button = MagicMock(spec=Button)
        self.open_editor_button = MagicMock(spec=Button)

        self.widget_map = {
            "#osa_path_status": self.osa_status,
            "#etc_path_status": self.etc_status,
            "#status_message": self.status_message,
            "#clone_osa": self.clone_button,
            "#custom_osa_path": self.custom_osa_button,
            "#inventory_config": self.proceed_config_button,
            "#network_config": self.proceed_network_button,
            "#service_config": self.proceed_service_button,
            "#init_config_dir": self.init_config_button,
            "#custom_config_path": self.custom_config_button,
            "#open_editor": self.open_editor_button,
        }

        self.screen.query_one = MagicMock(side_effect=lambda x, y=None: self.widget_map.get(x))

    @patch("openstack_ansible_wizard.screens.initial.Path")
    def test_check_paths_osa_exists_config_exists(self, mock_path):
        # Setup mocks to simulate both paths existing and valid
        mock_osa_path = MagicMock()
        mock_etc_path = MagicMock()

        def path_side_effect(arg):
            if str(arg).endswith("generate.py"):
                m = MagicMock()
                m.is_file.return_value = True
                return m
            if str(arg).endswith("openstack_user_config.yml"):
                m = MagicMock()
                m.is_file.return_value = True
                return m
            if arg == self.screen.osa_clone_dir:
                return mock_osa_path
            if arg == self.screen.osa_conf_dir:
                return mock_etc_path
            return MagicMock()

        mock_path.side_effect = path_side_effect
        mock_osa_path.is_dir.return_value = True
        mock_etc_path.is_dir.return_value = True

        self.screen.check_paths()

        # Verify OSA status update
        self.osa_status.update.assert_called()
        args, _ = self.osa_status.update.call_args
        self.assertIn("exists", args[0])
        self.assertIn("green", args[0])

        # Verify Config status update
        self.etc_status.update.assert_called()
        args, _ = self.etc_status.update.call_args
        self.assertIn("exists", args[0])
        self.assertIn("green", args[0])

        # Verify buttons enabled
        self.assertTrue(self.open_editor_button.display)
        self.assertFalse(self.open_editor_button.disabled)
        self.assertFalse(self.proceed_config_button.disabled)

    @patch("openstack_ansible_wizard.screens.initial.Path")
    def test_check_paths_osa_missing(self, mock_path):
        mock_osa_path = MagicMock()
        mock_etc_path = MagicMock()

        def path_side_effect(arg):
            if arg == self.screen.osa_clone_dir:
                return mock_osa_path
            if arg == self.screen.osa_conf_dir:
                return mock_etc_path
            return MagicMock()

        mock_path.side_effect = path_side_effect
        mock_osa_path.is_dir.return_value = False
        mock_etc_path.is_dir.return_value = True

        self.screen.check_paths()

        self.osa_status.update.assert_called()
        args, _ = self.osa_status.update.call_args
        self.assertIn("does not exist", args[0])
        self.assertIn("red", args[0])

        self.assertFalse(self.clone_button.disabled)

    @patch("openstack_ansible_wizard.screens.initial.Path")
    def test_check_paths_config_missing(self, mock_path):
        mock_osa_path = MagicMock()
        mock_etc_path = MagicMock()

        def path_side_effect(arg):
            if str(arg).endswith("generate.py"):
                m = MagicMock()
                m.is_file.return_value = True
                return m
            if arg == self.screen.osa_clone_dir:
                return mock_osa_path
            if arg == self.screen.osa_conf_dir:
                return mock_etc_path
            return MagicMock()

        mock_path.side_effect = path_side_effect
        mock_osa_path.is_dir.return_value = True
        mock_etc_path.is_dir.return_value = False

        self.screen.check_paths()

        self.etc_status.update.assert_called()
        args, _ = self.etc_status.update.call_args
        self.assertIn("does not exist", args[0])

        self.assertTrue(self.init_config_button.display)
        self.assertFalse(self.init_config_button.disabled)
        self.assertTrue(self.proceed_config_button.disabled)


class TestInitialCheckScreenAsync(unittest.IsolatedAsyncioTestCase):

    @patch("openstack_ansible_wizard.screens.initial.CloneOSAScreen")
    @patch("openstack_ansible_wizard.screens.initial.Path")
    async def test_clone_repo(self, MockPath, MockCloneScreen):
        new_path = "/new/osa/path"

        # Create a mock screen instance
        mock_screen = MagicMock(spec=InitialCheckScreen)
        mock_screen.app.push_screen_wait = AsyncMock(return_value=new_path)
        mock_screen.osa_clone_dir = "/old/path"

        # Mock Path checks for check_paths (if check_paths was called directly, but we mock check_paths)
        MockPath.return_value.is_dir.return_value = True

        # Call the wrapped method with the mock screen
        await InitialCheckScreen.clone_repo.__wrapped__(mock_screen)

        mock_screen.app.push_screen_wait.assert_called_once()
        self.assertEqual(mock_screen.osa_clone_dir, new_path)
        mock_screen.check_paths.assert_called_once()

    @patch("openstack_ansible_wizard.screens.initial.PathInputScreen")
    @patch("openstack_ansible_wizard.screens.initial.Path")
    async def test_enter_custom_osa_path(self, MockPath, MockPathInputScreen):
        custom_path = "/custom/osa"

        mock_screen = MagicMock(spec=InitialCheckScreen)
        mock_screen.app.push_screen_wait = AsyncMock(return_value=custom_path)
        mock_screen.osa_clone_dir = "/old/path"

        await InitialCheckScreen.enter_custom_osa_path.__wrapped__(mock_screen)

        mock_screen.app.push_screen_wait.assert_called_once()
        self.assertEqual(mock_screen.osa_clone_dir, custom_path)
        mock_screen.check_paths.assert_called_once()

    @patch("openstack_ansible_wizard.screens.initial.ConfirmExitScreen")
    @patch("openstack_ansible_wizard.screens.initial.file_copy")
    @patch("openstack_ansible_wizard.screens.initial.p_run")
    @patch("openstack_ansible_wizard.screens.initial.Path")
    async def test_init_config_dir(self, MockPath, MockRun, MockCopy, MockConfirm):

        mock_screen = MagicMock(spec=InitialCheckScreen)
        mock_screen.app.push_screen_wait = AsyncMock(return_value=True)
        mock_screen.osa_conf_dir = "/etc/openstack_deploy"
        mock_screen.osa_clone_dir = "/opt/openstack-ansible"

        mock_conf_path = MagicMock()
        mock_osa_path = MagicMock()

        def path_side_effect(arg):
            if arg == mock_screen.osa_conf_dir:
                return mock_conf_path
            if arg == mock_screen.osa_clone_dir:
                return mock_osa_path
            return MagicMock()

        MockPath.side_effect = path_side_effect

        await InitialCheckScreen.initialized_osa_config_dir.__wrapped__(mock_screen)

        mock_screen.app.push_screen_wait.assert_called_once()
        mock_screen.check_paths.assert_called_once()
