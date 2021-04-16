# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import setup, find_packages


setup_args = dict(
    name="picosvg",
    use_scm_version={"write_to": "src/picosvg/_version.py"},
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    entry_points={
        'console_scripts': [
            'picosvg=picosvg.picosvg:main',
        ],
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "absl-py>=0.9.0",
        "dataclasses>=0.7; python_version < '3.7'",
        "lxml>=4.0",
        "skia-pathops>=0.6.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-clarity",
            "black==20.8b1",
            "pytype==2020.11.23; python_version < '3.9'",
        ],
    },
    python_requires=">=3.6",

    # this is for type checker to use our inline type hints:
    # https://www.python.org/dev/peps/pep-0561/#id18
    package_data={"picosvg": ["py.typed"]},

    # metadata to display on PyPI
    author="Rod S",
    author_email="rsheeter@google.com",
    description=(
        "Exploratory utility for svg simplification, "
        "meant for use playing with COLR fonts"
    ),
)


if __name__ == "__main__":
    setup(**setup_args)
