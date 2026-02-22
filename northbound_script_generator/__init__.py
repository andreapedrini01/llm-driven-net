"""
Northbound Script Generator Module

A self-contained module for generating and executing network configuration scripts
for SDN controllers (RYU and ComnetsEMU).
"""

__version__ = "1.0.0"
__author__ = "Northbound Script Generator Team"

from .northbound_script import NorthboundScript

__all__ = ["NorthboundScript"]
