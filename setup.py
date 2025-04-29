from setuptools import setup, find_packages

setup(
    name="controlm-xml-automation",
    version="0.1.0",
    description="Utilities for automating Control-M XML modifications and environment promotion.",
    author="Ben Kaan",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        # Only pytest is required for testing, not for runtime
    ],
    python_requires=">=3.7",
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
