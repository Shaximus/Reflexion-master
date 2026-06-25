#!/usr/bin/env python3
"""
TRANSPORT SHIM
Re-exports everything from twitter_transport_interface.py
This allows imports to use 'twitter_transport' as expected.
"""

# Re-export everything from the actual module
from twitter_transport_interface import *

# Ensure the module appears correctly named
__all__ = [
    'TransportResponse',
    'ITwitterTransport', 
    'RyanAdapter',
    'TwitterOfficialAdapter',
    'TransportFactory',
    'TransportWatcher'
]
