from setuptools import setup, find_packages

setup(
    name="emailfilter",
    version="1.0.0",
    description="A Python application for filtering and processing emails",
    author="Tom Fagerland",
    author_email="tom.fagerland@schibsted.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "pyyaml",
        "imapclient",
        "openai>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "black",
            "isort",
            "mypy",
            "types-pyyaml",
            "types-requests",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 