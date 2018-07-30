from pimsviewer import Viewer
import click


@click.command()
@click.argument('filename', required=False)
def run(filename):
    app = Viewer(filename)
    app.run()


if __name__ == '__main__':
    run()
