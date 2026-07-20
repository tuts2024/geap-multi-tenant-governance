import os
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Prevent urllib3 from using PyOpenSSL, which contains a bug causing
# "ValueError: Context has already been used to create a Connection"
# when OTEL span exporter attempts to push telemetry after an HTTP error.
try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.extract_from_urllib3()
except Exception:
    pass

# Bypass SSL verification globally for standard libraries to fix proxy interception issues with telemetry
import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

from .agent import root_agent

__all__ = ["root_agent"]
