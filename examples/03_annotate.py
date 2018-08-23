import trackpy as tp
from os import path
from pimsviewer import Viewer, AnnotatePlugin
from pims import pipeline

@pipeline
def as_grey(frame):
    return 0.2125 * frame[:, :, 0] + 0.7154 * frame[:, :, 1] + 0.0721 * frame[:, :, 2]

filename = path.join(path.dirname(path.realpath(__file__)), '../screenshot.png')

viewer = Viewer(filename)

f = tp.batch(as_grey(viewer.reader), diameter=15)
plugin = AnnotatePlugin(viewer, f)

viewer.run()
