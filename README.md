# evtc-anonymizer
A simple and stupid script that replaces character and account names in 
uncompressed .evtc and compressed .zevtc files, the guild is also replaced with [ArenaNet] by default.

## Installation
Simply clone the repo and run locally or install it with pip.  
`pip install git+https://github.com/Invisi/python-evtc-anonymizer#egg=evtc`

## Usage
`python -m evtc [--pov] [--uncompressed] [--keep-guilds] evtc-file`  
`--pov` is an optional parameter to keep the pov's name in the file.  
`--keep-guilds`/`-G` will keep the original guilds and not replace them.
`--uncompressed`/`-U` will output an uncompressed log.  

For example: `python -m evtc 20191216-210251.evtc`, the generated file will be 
`20191216-210251-anonymized.zevtc`.
