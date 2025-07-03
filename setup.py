"""
Setup script for the mafia modeling project.
"""
from setuptools import setup, find_packages

setup(
    name="mafia-modeling",
    version="0.1.0",
    description="Mafia game modeling and AI development",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "torch",
        "numpy>=1.26.0",
        "pytest>=7.4.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.1",
            "coverage>=7.3.0",
        ]
    },
)
