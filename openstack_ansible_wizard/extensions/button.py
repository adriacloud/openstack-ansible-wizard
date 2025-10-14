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

from textual import events
from textual.widgets import Button


class NavigableButton(Button):
    """A button that allows navigation to sibling buttons using arrow keys."""

    async def _on_key(self, event: events.Key) -> None:
        """Handle key presses for arrow key navigation."""
        if event.key == "left":
            event.prevent_default()
            self.screen.focus_previous()
        elif event.key == "right":
            event.prevent_default()
            self.screen.focus_next()
        else:
            # For all other keys, let the base Button class handle them
            await super()._on_key(event)
