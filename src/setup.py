import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="opendsp",
    version="0.9.1",
    author="DSP Human interface service for headless devices",
    author_email="contact@midilab.co",
    description="A small example package",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="http://midilab.co/opendspd",
    packages=setuptools.find_packages(),
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)