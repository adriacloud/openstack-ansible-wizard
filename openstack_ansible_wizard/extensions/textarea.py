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
from textual.widgets import TextArea


class YAMLTextArea(TextArea):
    def _on_key(self, event: events.Key) -> None:
        if event.character == "(":
            self.insert("()")
            self.move_cursor_relative(columns=-1)
            event.prevent_default()

        if event.character == "[":
            self.insert("[]")
            self.move_cursor_relative(columns=-1)
            event.prevent_default()

        if event.character == "{":
            self.insert("{}")
            self.move_cursor_relative(columns=-1)
            event.prevent_default()

        if event.key == "enter":
            event.prevent_default()
            original_row, original_column = self.cursor_location
            self.insert("\n")
            if original_row < 0:
                return
            previous_line_text = self.get_line(original_row).plain

            # Calculate base indentation from previous line
            current_indent = ""
            for char in previous_line_text:
                if char == " " or char == "\t":
                    current_indent += char
                else:
                    break

            # Apply YAML-specific indentation rules
            new_indent = current_indent
            stripped_prev_line = previous_line_text.strip()

            if stripped_prev_line.endswith(":"):
                # If previous line ends with a colon, increase indent by 2 spaces
                new_indent += "  "

            # Insert the calculated indent on the new line
            if new_indent:
                self.insert(new_indent)
