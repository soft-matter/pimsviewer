from os import path
from pimsviewer import Viewer

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')
viewer = Viewer(filename)
viewer.run()
