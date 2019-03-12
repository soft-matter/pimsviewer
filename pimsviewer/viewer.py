import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as font

import numpy as np
import pygubu
from tkinter.filedialog import askopenfilename
from tkinter import filedialog, messagebox

import matplotlib as mpl
mpl.use("TkAgg")
from matplotlib import rcParams
import matplotlib.backends.tkagg as tkagg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import pims
from slicerator import pipeline
from pims import export
from pims.display import to_rgb
from pims.utils.sort import natural_keys
from functools import lru_cache

from os import listdir, path
from os.path import isfile, join, realpath
from fractions import Fraction
from .utils import get_supported_extensions, drop_dot, to_rgb_uint8
from .navigation_toolbar_pims import NavigationToolbarPims
from .plugins import ColorPlugin
import io

# Remove once PIMS is updated
try:
    from nd2reader import ND2Reader
except ImportError:
    pass

CURRENT_DIR = path.abspath(path.dirname(__file__))
fps = 5

class Viewer:
    def __init__(self, filename=None):
        # 1: Create a builder
        self.builder = builder = pygubu.Builder()

        # 2: Load an ui file
        builder.add_from_file(path.join(CURRENT_DIR, 'interface.ui'))
        
        # 3: Create the toplevel widget.
        self.mainwindow = builder.get_object('Toplevel_1')
        self.mainwindow.protocol("WM_DELETE_WINDOW", self.quit)
        self._dpi = self.mainwindow.winfo_fpixels('1i')
        self.frame = builder.get_object('Frame_1')
        self.frame.pack(fill=tk.BOTH, expand=True)

        # 4: Set main menu
        self.mainmenu = menu = builder.get_object('Menu_1', self.mainwindow)
        self.mainwindow.config(menu=menu)

        self.pluginmenu = builder.get_object('PluginsMenu', self.mainmenu)
        #@TODO: make a more general method to initialize plugins
        ColorPlugin.add_menu_item(self, self.pluginmenu)

        self.statusbar = builder.get_object('StatusBar')

        # Rest
        self.reader = None
        self.process_funcs = {}
        self._slider_job = None
        self.slider_frame = self.builder.get_object('SliderFrame')
        self.sliders = {}
        self.configure_sliders()
        self._playing = None
        self._play_job = None
        self.filename = filename
        self.figure, self.ax = self.create_figure()
        self._cache_figure, self._cache_ax = self.create_figure()
        self.index = {}
        self.canvas_frame = builder.get_object('CanvasFrame')
        self.toolbar = None
        self.canvas, self._cache_canvas = self.init_canvas()
        self._cache_t = None
        self.image = None
        self._cache_image = None

        # 7: Connect callback functions
        builder.connect_callbacks(self)
        self.set_accelerators()

        if self.filename is not None:
            self.open_file()

    def create_figure(self):
        fig = mpl.figure.Figure(figsize=(200/self._dpi, 200/self._dpi), dpi=self._dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis('off')
        return fig, ax

    def quit(self, event=None):
        if self._play_job is not None:
            self.mainwindow.after_cancel(self._play_job)
        if self._slider_job is not None:
            self.mainwindow.after_cancel(self._slider_job)
        self.mainwindow.quit()

    def run(self):
        self.mainwindow.mainloop()

    def open_file(self, event=None):
        if event is not None or self.filename is None:
            filename = askopenfilename()
            if len(filename) == 0:
                return
            self.filename = filename
        self.reader = pims.open(self.filename)
        self.update_statusbar()
        self.init_sliders()
        self.show_frame()

    def close_file(self, event=None):
        self.reader = self.filename = None
        self.update_statusbar()
        self.hide_all_sliders()
        self.ax.clear()
        self.ax.axis('off')
        self.canvas.draw()

    def merge_channels(self, image):
        if len(image.shape) == 3 and image.shape[2] == 3:
            return image

        return to_rgb(image)

    def change_merge_channels(self, event=None):
        self.show_frame()

    def show_frame(self):
        frame_no = self.sliders['t']['current'] - 1
        channel_no = self.sliders['c']['current'] - 1
        z_no = self.sliders['z']['current'] - 1

        if not hasattr(self.reader, 'sizes'):
            self.reader.sizes = {}
        if 'c' in self.reader.sizes:
            if 'z' in self.reader.sizes:
                self.index = {'t': frame_no, 'c': channel_no, 'z': z_no}
                index = dict(frame=frame_no, z=z_no, c=channel_no, merge=merge)
            else:
                self.index = {'t': frame_no, 'c': channel_no}
                merge = 'selected' in self.sliders['c']['merge_btn'].state()
                index = dict(frame=frame_no, c=channel_no, merge=merge)
        else:
            if 'z' in self.reader.sizes:
                self.index = {'t': frame_no, 'z': z_no}
                index = dict(frame=frame_no, z=z_no)
            else:
                self.index = {'t': frame_no}
                index = dict(frame=frame_no)

        self._imshow(**index)

    def get_processed_image(self, frame=0, z=None, c=None, merge=False):
        self.reader.iter_axes = 't'
        coords = {'t': frame}

        if c is not None:
            if z is not None:
                self.reader.bundle_axes = 'czyx'
                if merge:
                    image = self.reader[frame][:, z, :, :]
                    coords['z'] = z
                else:
                    image = self.reader[frame][c, z, :, :]
                    coords['z'] = z
                    coords['c'] = c
            else:
                self.reader.bundle_axes = 'cyx'
                if merge:
                    image = self.reader[frame][:, :, :]
                else:
                    image = self.reader[frame][c, :, :]
                    coords['c'] = c
        elif z is not None:
            self.reader.bundle_axes = 'zyx'
            image = self.reader[frame][z, :, :]
            coords['z'] = z
        else:
            self.reader.bundle_axes = 'yx'
            image = self.reader[frame][:, :]

        for fname in self.process_funcs:
            image.metadata['coords'] = coords
            image = self.process_funcs[fname](image)

        if merge:
            image = self.merge_channels(image)

        return image

    def add_process_function(self, name, function):
        self.process_funcs[name] = function

    def remove_process_function(self, name):
        try:
            del self.process_funcs[name]
        except KeyError:
            return

    @lru_cache(maxsize=128)
    def get_canvas_image(self, limits, frame=0, z=None, c=None, merge=False):
        image = self.get_processed_image(frame, z, c, merge)

        if self._cache_image is None:
            self._cache_image = self._cache_ax.imshow(image,
                                                      interpolation='none',
                                                      filternorm=False,
                                                      resample=False)
        else:
            self._cache_image.set_data(image)

        self._cache_ax.set_xlim(limits[0][0], limits[0][1])
        self._cache_ax.set_ylim(limits[1][0], limits[1][1])

        self._cache_canvas.draw()
        return self._cache_canvas.copy_from_bbox(self._cache_ax.bbox), image

    def _imshow(self, **kwargs):
        limits = (self.ax.get_xlim(), self.ax.get_ylim())
        canvas_image, image = self.get_canvas_image(limits, **kwargs)
        
        if self.image is None:
            self.image = self.ax.imshow(image, interpolation='none',
                                        filternorm=False, resample=False)

        self.canvas.restore_region(canvas_image)
        self.canvas.blit(self.ax.bbox)

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
        
        self._cache_t = None
        self.show_frame()
        self.prepopulate_cache()
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
                        self.sliders[prop]['fps'] = np.round(self.reader.frame_rate, 1)
                    except AttributeError:
                        self.sliders[prop]['fps'] = np.round(fps, 1)
                    self.builder.tkvariables.__getitem__('fps').set(self.sliders[prop]['fps'])
                    self._play_job = self.mainwindow.after(10, self.prepopulate_cache)

    def hide_all_sliders(self):
        for prop in self.sliders.keys():
            self.sliders[prop]['frame'].grid_remove()

    def configure_sliders(self):
        self.sliders['c'] = {
                'frame': self.builder.get_object('ChannelFrame', self.slider_frame),
                'value_label': self.builder.get_object('ChannelValue'),
                'play_btn': self.builder.get_object('ChannelPlayBtn'),
                'slider': self.builder.get_object('ChannelScale'),
                'merge_btn': self.builder.get_object('ChannelMerge'),
                'current': 1,
                'fps': fps
        }
        self.sliders['c']['merge_btn'].invoke()

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


        play_img = tk.PhotoImage(file=path.join(path.dirname(realpath(__file__)), "../images/play.png"))
        for prop in self.sliders.keys():
            self.sliders[prop]['play_btn'].configure(image=play_img, height=18, width=18, text='')
            self.sliders[prop]['play_btn'].image = play_img

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

    def configure_canvas(self, event):
        if self._play_job:
            self.mainwindow.after_cancel(self._play_job)
        
        self._cache_canvas.resize(event)

        self._cache_t = None
        self.show_frame()
        self.prepopulate_cache()

    def init_canvas(self):
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_frame)
        self.canvas.get_tk_widget().grid(row=1, column=0, pady=0, padx=0, sticky='nsew')
        self.toolbar = NavigationToolbarPims(self.canvas, self.canvas_frame, self.slider_frame)
        self.toolbar.grid(row=0, column=0, pady=0, padx=0)
        self.toolbar.update()

        self.canvas_frame.rowconfigure(0, weight=1)
        self.canvas_frame.rowconfigure(1, weight=100)

        message = self.toolbar.get_message_label()
        message.grid(row=0)

        self._cache_canvas = FigureCanvasTkAgg(self._cache_figure, master=self.mainwindow)

        self.canvas.mpl_connect('resize_event', self.configure_canvas)

        return self.canvas, self._cache_canvas

    def set_accelerators(self):
        self.mainwindow.bind_all("<Control-q>", self.quit)
        self.mainwindow.bind_all("<Control-o>", self.open_file)
        self.mainwindow.bind_all("<Control-O>", self.open_next_file)
        self.mainwindow.bind_all("<Alt-O>", self.open_previous_file)
        self.mainwindow.bind_all("<Control-w>", self.close_file)
        self.mainwindow.bind_all("<Control-e>", self.export_file)
        self.mainwindow.bind_all("<Control-s>", self.export_frame)

    def toggle_play_time(self):
        self.toggle_play('t')

    def toggle_play_channel(self):
        self.toggle_play('c')

    def toggle_play_z(self):
        self.toggle_play('z')

    def toggle_play(self, prop):
        self._cache_t = None
        if self._playing is None:
            self._playing = prop
            self.sliders[prop]['play_btn'].configure(text='⏸')
            self.sliders[prop]['play_btn'].update()
            if prop == 't':
                self.sliders[prop]['fps'] = np.round(self.builder.tkvariables.__getitem__('fps').get(), 1)
            play_fps = self.sliders[prop]['fps']
            if play_fps <= 0:
                play_fps = fps
            elif play_fps > 10.0:
                play_fps = 10.0
            timeout = int(round(1.0 / play_fps * 1000.0))
            if timeout < 1.0:
                timeout = 1.0
            self.update_statusbar("Playing axis '%s' @ %.1f FPS" % (prop,
                                  1.0/(timeout/1000.0)))
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
            self._play_job = self.mainwindow.after(10, self.prepopulate_cache)

    def prepopulate_cache(self):
        if self._playing is not None:
            return

        self._playing = None

        if self._play_job:
            self.mainwindow.after_cancel(self._play_job)

        if 't' not in self.reader.sizes:
            return

        if self._cache_t is None:
            self._cache_t = self.sliders['t']['current'] - 1

        current_t = self.sliders['t']['current'] - 1

        info = self.get_canvas_image.cache_info()
        if abs(self._cache_t-current_t) >= (info.maxsize-1):
            return

        index = {}
        frame_no = self._cache_t + 1
        channel_no = self.sliders['c']['current'] - 1
        z_no = self.sliders['z']['current'] - 1

        if 'c' in self.reader.sizes:
            if 'z' in self.reader.sizes:
                merge = 'selected' in self.sliders['c']['merge_btn'].state()
                index = {'frame': frame_no, 'c': channel_no, 'z': z_no,
                         'merge': merge}
            else:
                merge = 'selected' in self.sliders['c']['merge_btn'].state()
                index = {'frame': frame_no, 'c': channel_no, 'merge': merge}
        else:
            if 'z' in self.reader.sizes:
                index = {'frame': frame_no, 'z': z_no}
            else:
                index = {'frame': frame_no}

        limits = (self.ax.get_xlim(), self.ax.get_ylim())
        self.get_canvas_image(limits, **index)
        self._cache_t = frame_no
        self._play_job = self.mainwindow.after(10, self.prepopulate_cache)

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

        if timeout < 1.0:
            timeout = 1.0
        self._play_job = self.mainwindow.after(timeout, self.play, timeout, prop)

    def open_next_file(self, event=None, forward=True):
        if self.filename is None:
            self.open_file()

        supported_extensions = get_supported_extensions()

        current_directory = path.dirname(self.filename)
        file_list = self._get_all_files_in_dir(current_directory, extensions=supported_extensions)
        if len(file_list) < 2:
            self.update_statusbar(override='No file found for opening')
            return

        try:
            current_file_index = file_list.index(path.basename(self.filename))
        except ValueError:
            self.update_statusbar(override='No file found for opening')
            return

        next_index = current_file_index + 1 if forward else current_file_index - 1
        try:
            next_file = file_list[next_index]
        except IndexError:
            next_index = 0 if forward else -1
            next_file = file_list[next_index]

        self.filename = path.join(current_directory, next_file)
        self.open_file()

    def open_previous_file(self, event=None):
        self.open_next_file(forward=False)

    @staticmethod
    @lru_cache(maxsize=512)
    def _get_all_files_in_dir(directory, extensions=None):
        if extensions is None:
            file_list = [f for f in listdir(directory) if isfile(join(directory, f))]
        else:
            file_list = [f for f in listdir(directory) if isfile(join(directory, f))
                         and drop_dot(path.splitext(f)[1]) in extensions]

        return sorted(file_list, key=natural_keys)

    def export_file(self, event=None):
        filetypes = {'avi': 'H264 movie', 'wmv': 'Windows Media Player movie', 'mp4': 'MPEG4 movie', 'mov': 'MOV movie'}
        default_filetype = 'mp4'

        # Tk doesn't provide a way to choose a default filetype,
        # so we just have to put it first
        default_filetype_name = filetypes.pop(default_filetype)
        sorted_filetypes = ([(default_filetype, default_filetype_name)]
                            + sorted(filetypes.items()))
        tk_filetypes = [(name, '*.%s' % ext) for ext, name in sorted_filetypes]

        # adding a default extension seems to break the
        # asksaveasfilename dialog when you choose various save types
        # from the dropdown.  Passing in the empty string seems to
        # work - JDH!
        #defaultextension = self.canvas.get_default_filetype()
        defaultextension = ''
        initialdir = path.expanduser(rcParams['savefig.directory'])
        initialfile = path.splitext(path.basename(self.filename))[0] + '.%s' % default_filetype
        fname = filedialog.asksaveasfilename(
            master=self.mainwindow,
            title='Save the file',
            filetypes=tk_filetypes,
            defaultextension=defaultextension,
            initialdir=initialdir,
            initialfile=initialfile,
            )

        if fname in ["", ()]:
            return

        # Save dir for next time, unless empty str (i.e., use cwd).
        if initialdir != "":
            rcParams['savefig.directory'] = (path.dirname(str(fname)))
        try:
            # This method will handle the delegation to the correct type
            self._export_video(fname, rate=None)
        except Exception as e:
            messagebox.showerror("Error saving file", str(e))

    def export_frame(self, event=None):
        self.toolbar.save_figure()

    def _export_video(self, filename=None, rate=None, **kwargs):
            """For a list of kwargs, see pims.export"""
            # TODO Save the canvas instead of the reader (including annotations)
            presets = dict(avi=dict(codec='libx264', quality=23),
                           mp4=dict(codec='mpeg4', quality=5),
                           mov=dict(codec='mpeg4', quality=5),
                           wmv=dict(codec='wmv2', quality=0.005))

            ext = path.splitext(filename)[-1]
            if ext[0] == '.':
                ext = ext[1:]
            try:
                _kwargs = presets[ext]
            except KeyError:
                raise ValueError("Extension '.{}' is not a known format.".format(ext))

            _kwargs.update(kwargs)

            if rate is None:
                try:
                    rate = float(self.reader.frame_rate)
                except AttributeError or ValueError:
                    rate = 25.

            self.reader.iter_axes = 't'
            self.update_statusbar(override='Saving to "{}"'.format(filename))

            # PIMS v0.4 export() has a bug having to do with float precision
            # fix that here using limit_denominator() from fractions
            export(pipeline(to_rgb_uint8)(self.reader), filename, Fraction(rate).limit_denominator(66535), **kwargs)
            self.update_statusbar(override='Done saving to "{}"'.format(filename))
