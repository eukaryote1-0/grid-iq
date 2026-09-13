"""GridIQ engines package.

Each engine is a pure-Python module that consumes the evidence substrate in
``data/`` and returns a JSON-serialisable dict. Engines are importable without
the web server so they can be tested and run standalone.
"""
