from setuptools import setup, find_packages

setup(
    name="pipeman",
    version="0.1.0",
    description="A tool to manage and run data pipeline stages",
    author="CaneRig",
    packages=find_packages(),
    install_requires=[
        "pyyaml>=5.1",
    ],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "pipeline = pipeline_manager.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
)