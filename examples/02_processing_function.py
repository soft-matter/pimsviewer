"""
This example adds a processing function that adds an adjustable amount of noise
to an image. The amount of noise is tunable with a slider, which is displayed
on the right of the image window.
"""
import tkinter as tk
import numpy as np
from os import path
import pims
from pimsviewer import Viewer, Plugin

def add_noise(img, widget_values):
    if 'noise_level' in widget_values:
        noise_level = widget_values['noise_level']
    else:
        noise_level = 0
    img = img + np.random.random(img.shape) * noise_level / 100 * img.max()
    return img / np.max(img)

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

viewer = Viewer(filename)
AddNoise = Plugin(viewer, add_noise, 'Add noise', width=200)
AddNoise += tk.Scale(AddNoise, from_=0, to=200, orient=tk.HORIZONTAL, name='noise_level')
viewer.run()
