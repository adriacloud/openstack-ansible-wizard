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

import git


def get_git_version(path: str) -> str:
    """Return git repository current version

    This is separated as a function to cover varios scenarios of
    how a repository could be checked out. At the same time, it is
    limited with a simple describe right now, but with a potential
    to grow logic if/when needed.
    """
    repo = git.Repo(path)
    return repo.git.describe()
