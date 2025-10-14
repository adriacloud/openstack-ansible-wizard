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

import os
import urllib.request as request
from urllib.error import URLError, HTTPError
import yaml


def path_writable(path: str, parent: bool = False) -> bool:
    """Identify if current or parent part is writable for the script"""
    if parent:
        path = os.path.dirname(path)

    return os.access(path, os.W_OK)


def get_openstack_series(releases_uri: str) -> list:
    """Fetch and parse currently maintained releases from upstream repository"""

    uri = os.path.join(releases_uri, 'data/series_status.yaml')
    try:
        with request.urlopen(uri) as response:
            openstack_series = yaml.load(response, Loader=yaml.Loader)
    except HTTPError as e:
        print('The server couldn\'t fulfill the request.')
        print('Error code: ', e.code)
        openstack_series = []
    except URLError as e:
        print('We failed to reach a server.')
        print('Reason: ', e.reason)
        openstack_series = []

    active_series = [series for series in openstack_series if series['status'] == 'maintained']
    return active_series


def get_osa_versions(releases_uri: str, release: str) -> list:
    """Fetch and parse available versions for given release"""
    uri = os.path.join(releases_uri, f'deliverables/{release}/openstack-ansible.yaml')
    try:
        with request.urlopen(uri) as response:
            osa_deliverable = yaml.load(response, Loader=yaml.Loader)
    except HTTPError as e:
        print('The server couldn\'t fulfill the request.')
        print('Error code: ', e.code)
        osa_deliverable = {}
    except URLError as e:
        print('We failed to reach a server.')
        print('Reason: ', e.reason)
        osa_deliverable = {}

    osa_versions = [version['version'] for version in osa_deliverable.get('releases', [])]
    return osa_versions
