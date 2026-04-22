"""
Name: Ryan, Andrew, Chris, Diego
Date: 2026-04-22
Course: CST 205 - Multimedia Programming
Final Project

A Flask app that lets you click on mood board and play music
based on the emotion you picked. Using spotify api to get playlist.
"""

from flask import Flask, render_template, abort
from flask_bootstrap import Bootstrap5
from PIL import Image
from pathlib import Path
import random

from image_info import image_info