"""Setup configuration for Mailmind."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mailmind",
    version="0.1.0",
    author="Tom Fagerland",
    author_email="tom@fager.land",
    description="An AI-powered email management and categorization tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tomfagerland/mailmind",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Email",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "torch>=2.0.0",
        "transformers>=4.30.0",
        "imapclient>=2.3.1",
        "pyyaml>=6.0.1",
        "tqdm>=4.65.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "wandb>=0.15.0",
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0",
        "black>=23.7.0",
        "isort>=5.12.0",
        "flake8>=6.1.0",
        "mypy>=1.5.0",
    ],
    entry_points={
        "console_scripts": [
            "mailmind=mailmind.inference.cli:main",
            "mailmind-train=mailmind.training.cli:main",
        ],
    },
) 