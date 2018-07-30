"""
This example adds a processing function that adds an adjustable amount of noise
to an image. The amount of noise is tunable with a slider, which is displayed
on the right of the image window.
"""
import numpy as np
from os import path
import pims
from pimsviewer import Viewer, ProcessPlugin, Slider

# The processing function
def add_noise(img, noise_level):
    return img + np.random.random(img.shape) * noise_level / 100 * img.max()

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

AddNoise = ProcessPlugin(add_noise, 'Add noise', dock='right')
AddNoise += Slider('noise_level', low=0, high=100, value=10,
                   orientation='vertical')
viewer = Viewer(filename) + AddNoise
viewer.run()
