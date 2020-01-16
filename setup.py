"""Just a toy, enough setuptools to be able to install.
"""
from setuptools import setup, find_packages

setup(
    name="nanosvg",
    version="0.1",
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    entry_points={
        'console_scripts': [
            'nanosvg=nanosvg.nanosvg:main',
        ],
    },

    install_requires=["lxml>=4.0", "skia-pathops>=0.2",],

    # metadata to display on PyPI
    author="Rod S",
    author_email="rsheeter",
    description=(
        "Exploratory utility for svg simplification, "
        "meant for use playing with COLR fonts"
    ),
)
