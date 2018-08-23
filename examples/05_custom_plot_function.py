import trackpy as tp
from pimsviewer import Viewer, PlottingPlugin
from os import path
from pims import pipeline
import tkinter as tk

@pipeline
def as_grey(frame):
    return 0.2125 * frame[:, :, 0] + 0.7154 * frame[:, :, 1] + 0.0721 * frame[:, :, 2]

def locate_and_plot(image, widget_values, ax):
    radius = widget_values['radius'] if 'radius' in widget_values else 2
    minmass = widget_values['minmass'] if 'minmass' in widget_values else 1
    separation = widget_values['separation'] if 'separation' in widget_values else 1

    grey_image = as_grey(image)

    f = tp.locate(grey_image, diameter=radius * 2 + 1, minmass=minmass,
                  separation=separation)
    if len(f) == 0:
        return image
    ax.plot(f['x'], f['y'], markersize=15, markeredgewidth=2,
            markerfacecolor='none', markeredgecolor='r',
            marker='o', linestyle='none')
    return image

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

viewer = Viewer(filename)

plugin = PlottingPlugin(viewer, locate_and_plot)

plugin += tk.Scale(plugin, from_=2, to=20, orient=tk.HORIZONTAL, name='radius', resolution=7)
plugin += tk.Scale(plugin, from_=1, to=100, orient=tk.HORIZONTAL, name='separation', resolution=7)
plugin += tk.Scale(plugin, from_=1, to=10000, orient=tk.HORIZONTAL, name='minmass', resolution=100)

viewer.run()

