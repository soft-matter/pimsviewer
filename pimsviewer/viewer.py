import os
try:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.font as font
except ImportError: # Python 2
    import Tkinter as tk
    import ttk
    import tkFont as font

import pygubu
from tkinter.filedialog import askopenfilename
import matplotlib as mpl

mpl.use("TkAgg")

import matplotlib.backends.tkagg as tkagg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pims

from nd2reader import ND2Reader

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
fps = 5

class Viewer:
    def __init__(self, filename, reader_class):
        # 1: Create a builder
        self.builder = builder = pygubu.Builder()

        # 2: Load an ui file
        builder.add_from_file(os.path.join(CURRENT_DIR, 'interface.ui'))
        
        # 3: Create the toplevel widget.
        self.mainwindow = builder.get_object('Toplevel_1')
        self._dpi = self.mainwindow.winfo_fpixels('1i')
        self.frame = builder.get_object('Frame_1')
        self.frame.pack(fill=tk.BOTH, expand=True)

        # 4: Set main menu
        self.mainmenu = menu = builder.get_object('Menu_1', self.mainwindow)
        self.mainwindow.config(menu=menu)

        self.statusbar = builder.get_object('StatusBar')

        # 5: Program specific code
        self.filename = filename
        self.figure, self.ax = self.create_figure()
        self.canvas_frame = builder.get_object('CanvasFrame')
        self.canvas = self.init_canvas()
        self.photo = None
        self.reader = None

        # 6: sliders
        self._slider_job = None
        self.slider_frame = self.builder.get_object('SliderFrame')
        self.sliders = {}
        self.configure_sliders()
        self._playing = None
        self._play_job = None

        # 7: Connect callback functions
        builder.connect_callbacks(self)
        self.mainwindow.bind("<Configure>", self.resize)
        self.set_accelerators()

        if self.filename is not None:
            self.open_file()

    def create_figure(self):
        fig = mpl.figure.Figure(figsize=(200/self._dpi, 200/self._dpi), dpi=self._dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')
        return fig, ax

    def quit(self, event=None):
        self.mainwindow.quit()

    def run(self):
        self.mainwindow.mainloop()

    def open_file(self, event=None):
        if event is not None:
            self.filename = askopenfilename()
            if len(self.filename) == 0:
                return
        self.reader = pims.open(self.filename)
        self.show_frame()
        self.update_statusbar()
        self.init_sliders()

    def show_frame(self):
        frame_no = self.sliders['t']['current'] - 1
        channel_no = self.sliders['c']['current'] - 1
        z_no = self.sliders['z']['current'] - 1

        if not hasattr(self.reader, 'sizes'):
            self.reader.sizes = {}
        if 'c' in self.reader.sizes:
            if 'z' in self.reader.sizes:
                self.reader.bundle_axes = 'czyx'
                self.ax.imshow(self.reader[frame_no][channel_no, z_no, :, :])
            else:
                self.reader.bundle_axes = 'cyx'
                self.ax.imshow(self.reader[frame_no][channel_no, :, :])
        else:
            if 'z' in self.reader.sizes:
                self.reader.bundle_axes = 'zyx'
                self.ax.imshow(self.reader[frame_no][z_no, :, :])
            else:
                self.ax.imshow(self.reader[frame_no])
        self.draw_figure()

    def on_slider_change(self, event=None):
        if self._slider_job:
            self.mainwindow.after_cancel(self._slider_job)
        self._slider_job = self.mainwindow.after(200, self._on_slider_change)

    def _on_slider_change(self, override_playing=False):
        if self._playing is not None and not override_playing:
            self._slider_job = None
            return

        for prop in self.sliders.keys():
            if prop in self.reader.sizes and self.reader.sizes[prop] > 1:
                value = int(round(self.sliders[prop]['slider'].get()))
                if value != self.sliders[prop]['current']:
                    self.sliders[prop]['value_label'].configure(text='%d/%d' % (value, self.reader.sizes[prop]))
                    self.sliders[prop]['value_label'].update()
                    self.sliders[prop]['current'] = value
        
        self.show_frame()
        self._slider_job = None

    def init_sliders(self):
        if self.reader is None:
            self.hide_all_sliders()

        if not hasattr(self.reader, 'sizes'):
            self.hide_all_sliders()

        for prop in self.sliders.keys():
            if prop not in self.reader.sizes or self.reader.sizes[prop] <= 1:
                self.sliders[prop]['frame'].grid_remove()
                self.sliders[prop]['frame'].update()
            else:
                self.sliders[prop]['frame'].grid()
                self.sliders[prop]['frame'].update()
                self.sliders[prop]['value_label'].configure(text='%d/%d' % (1, self.reader.sizes[prop]))
                self.sliders[prop]['value_label'].update()
                self.sliders[prop]['slider'].configure(from_=1, to=self.reader.sizes[prop])
                self.sliders[prop]['slider'].update()

                if prop == 't':
                    try:
                        self.sliders[prop]['fps'] = self.reader.frame_rate
                    except AttributeError:
                        self.sliders[prop]['fps'] = fps


    def hide_all_sliders(self):
        for prop in self.sliders.keys():
            self.sliders[prop]['frame'].grid_remove()

    def configure_sliders(self):
        self.sliders['c'] = {
                'frame': self.builder.get_object('ChannelFrame', self.slider_frame),
                'value_label': self.builder.get_object('ChannelValue'),
                'play_btn': self.builder.get_object('ChannelPlayBtn'),
                'slider': self.builder.get_object('ChannelScale'),
                'current': 1,
                'fps': fps
        }

        self.sliders['t'] = {
                'frame': self.builder.get_object('TimeFrame', self.slider_frame),
                'value_label': self.builder.get_object('TimeValue'),
                'play_btn': self.builder.get_object('TimePlayBtn'),
                'slider': self.builder.get_object('TimeScale'),
                'current': 1,
                'fps': fps
        }

        self.sliders['z'] = {
                'frame': self.builder.get_object('ZFrame', self.slider_frame),
                'value_label': self.builder.get_object('ZValue'),
                'play_btn': self.builder.get_object('ZPlayBtn'),
                'slider': self.builder.get_object('ZScale'),
                'current': 1,
                'fps': fps
        }

        self.hide_all_sliders()

    def update_statusbar(self, override=None):
        if override is not None:
            text = override
        elif self.filename is not None:
            filename = self.filename
            if len(filename) > 35:
                filename = '...' + filename[-35:]
            text = 'Current file: "%s"' % filename
        else:
            text = 'Ready'

        self.statusbar.configure(text=text)
        self.statusbar.update()

    def init_canvas(self):
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_frame)
        self.canvas.draw_idle()
        self.canvas.get_tk_widget().grid(row=0, column=0, pady=0, padx=0, sticky='nsew')
        return self.canvas

    def draw_figure(self):
        cpw, cph = self.canvas.get_width_height()
        self.figure.set_size_inches(cpw/self._dpi, cph/self._dpi, forward=True)
        self.canvas.draw_idle()

    def set_accelerators(self):
        self.mainwindow.bind_all("<Control-q>", self.quit)
        self.mainwindow.bind_all("<Control-o>", self.open_file)

    def resize(self, event=None):
        self.draw_figure()

    def toggle_play_time(self):
        self.toggle_play('t')

    def toggle_play_channel(self):
        self.toggle_play('c')

    def toggle_play_z(self):
        self.toggle_play('z')

    def toggle_play(self, prop):
        if self._playing is None:
            self._playing = prop
            self.sliders[prop]['play_btn'].configure(text='⏸')
            self.sliders[prop]['play_btn'].update()
            timeout = int(round(1.0 / self.sliders[prop]['fps'] * 1000.0))
            self.update_statusbar("Playing axis '%s' @ %.1f FPS" % (prop, self.sliders[prop]['fps']))
            if self._play_job:
                self.mainwindow.after_cancel(self._play_job)
            self._play_job = self.mainwindow.after(timeout, self.play, timeout, prop)
        elif self._playing is prop:
            if self._play_job:
                self.mainwindow.after_cancel(self._play_job)
            self.sliders[prop]['play_btn'].configure(text='⏵')
            self.sliders[prop]['play_btn'].update()
            self.update_statusbar()
            self._playing = None

    def play(self, timeout, prop):
        if self._playing is None or self._playing != prop:
            return

        if self._play_job:
            self.mainwindow.after_cancel(self._play_job)

        new_value = self.sliders[prop]['current'] + 1
        if new_value > self.reader.sizes[prop]:
            new_value = 1
        self.sliders[prop]['slider'].set(new_value)
        self._on_slider_change(override_playing=True)

        self.show_frame()

        self._play_job = self.mainwindow.after(timeout, self.play, timeout, prop)
