from pimsviewer import Viewer
from pimsviewer.utils import get_available_readers
import click


def get_available_readers_dict():
    available_reader_classes = get_available_readers()
    available_readers = {cls.__name__: cls for cls in available_reader_classes}
    return available_readers


@click.command()
@click.argument('file', required=False)
@click.option('--reader-class', type=click.Choice(get_available_readers_dict().keys()),
              help='Reader with which to open the file.')
def run(file, reader_class):
    app = Viewer(file, reader_class)
    app.run()


if __name__ == '__main__':
    run()
