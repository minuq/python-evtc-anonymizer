import setuptools

setuptools.setup(
    name="evtc",
    version="0.0.1",
    author="Yannick Linke",
    author_email="invisi@0x0f.net",
    description="A simple script to replace names inside arcdps's combat logs",
    url="https://github.com/Invisi/python-evtc-anonymizer",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)