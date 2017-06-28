try:
    from nd2reader import ND2Reader
except ImportError(ND2Reader):
    pass

from pimsviewer import Viewer


def run():
    viewer = Viewer()
    viewer.show()
