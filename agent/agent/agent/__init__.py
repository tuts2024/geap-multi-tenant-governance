import os
import sys

# Prevent urllib3 from using PyOpenSSL, which contains a bug causing
# "ValueError: Context has already been used to create a Connection"
# when OTEL span exporter attempts to push telemetry after an HTTP error.
try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.extract_from_urllib3()
except Exception:
    pass

from .agent import root_agent

__all__ = ["root_agent"]
