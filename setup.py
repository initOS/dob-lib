import os

from setuptools import find_packages, setup


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()


deps = [
    "black",
    "coverage",
    "debugpy",
    "flake8",
    "git-aggregator",
    "ipython",
    "isort>=4.3.10",
    "pylint_odoo",
    "pytest-cov",
    "PyYAML",
]

if not os.getenv("DISABLE_PYTEST_ODOO"):
    deps.append("pytest-odoo")

setup(
    name="doblib",
    version="0.10.0",
    author="initOS GmbH",
    author_email="info@initos.com",
    description="Management tool for Odoo installations",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    license="Apache License 2.0",
    keywords="odoo environment management",
    url="https://github.com/initos/dob-lib",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=deps,
    entry_points={"console_scripts": ["dob = doblib.__main__:main"]},
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
    python_requires=">=3.6",
)
