from setuptools import setup

setup(
    name="hashbrownie",
    version="0.1.0",
    py_modules=["hashbrownie"],
    entry_points={
        "console_scripts": [
            "hashbrownie=hashbrownie:main",
        ],
    },
    install_requires=["rich>=13.0.0"],
    python_requires=">=3.10",
)
