#!/usr/bin/env python
# Copyright (C) 2014 Alexandre Quessy
# See LICENSE (LGPL 2)
"""
Video player for live arts.
Usage: Create video a.mov, b.mov and c.mov.
       Put them all in the same directory
       Then, run this script and press letters A, B, C to switch video.
       They should all play in loops.
Deps:  Python, Clutter, Clutter-GStreamer
Bugs:  When I change the clip being played, the eos signal of the video texture is not triggered anymore.
"""
import os
import sys
from gi.repository import Clutter
from gi.repository import ClutterGst
import json


class Configuration(object):
    """
    Holds the configuration option values.
    """
    def __init__(self):
        self.filenames = []
        self.window_width = 1024
        self.window_height = 768
        self.start_fullscreen = True
        self.show_cursor = False
        self.initial_clip_number = 0
        # TODO: add image on top
        # TODO: vertial-align
        # TODO: horizontal-align
        # TODO: horizontal-fill
        # TODO: vertical-fill


class Application(object):
    """
    Video player.
    """
    def __init__(self, config):
        BLACK = Clutter.Color.new(0x00, 0x00, 0x00, 0x00)
        WHITE = Clutter.Color.new(0xff, 0xff, 0xff, 0xff)
        TITLE = "Europlayer"
        FONT = "Sans Bold 14"
        HELP_TEXT = "Letters: choose clip.\n"
        HELP_TEXT += "F1: Help."
        HELP_TEXT += "Escape: Toggle fullscreen."
        HELP_TEXT += "Space: Fade to black."
        HELP_TEXT += "Ctrl-Q: Quit."
        #TODO: HELP_TEXT += "There is not config file for now."

        self._config = config
        self._is_fullscreen = False
        self._current_clip_number = self._config.initial_clip_number

        ClutterGst.init(sys.argv)
        self._stage = Clutter.Stage.get_default()
        self._stage.set_title(TITLE)
        self._stage.set_color(BLACK)
        self._stage.set_size(self._config.window_width,
            self._config.window_height)
        self._stage.set_minimum_size(640, 480)
        if self._config.start_fullscreen:
            self._stage.set_fullscreen(True)
            self._is_fullscreen = True
        if not self._config.show_cursor:
            self._stage.hide_cursor()
        #self._stage.connect("event", self._stage_event_cb)
        self._stage.connect("key-press-event", self._stage_key_press_event_cb)

        # Create the video texture
        self._video_texture = ClutterGst.VideoTexture()
        self._stage.connect("allocation-changed",
            self._stage_allocation_changed_cb)
        self._stage.connect("destroy", lambda x: self.quit)
        self._video_texture.connect_after("size-change",
            self._video_texture_size_change_cb)

        # Text labels
        self._info_label = Clutter.Text().new_full(FONT, "TODO", WHITE)
        self._info_label.hide()

        self._help_label = Clutter.Text().new_full(
            FONT, HELP_TEXT, WHITE)
        self._help_label.hide()

        self._stage.add_actor(self._video_texture)
        self._stage.add_actor(self._help_label)
        self._stage.add_actor(self._info_label)

        self._eos_handler_id = None
        self.play_clip_number(self._current_clip_number)

        self._stage.show()


    def quit(self):
        """
        Quits the application.
        """
        Clutter.main_quit()


    def _video_texture_eos_cb(self, media):
        print("eos")
        # FIXME: this is not where we should catch these
        try:
            # looping:
            media.set_progress(0.0)
            media.set_playing(True)
        except KeyboardInterrupt, e:
            print(e)
            self.quit()
            

    def _stage_allocation_changed_cb(self, stage, box, flags):
        self._resize_image()


    def _video_texture_size_change_cb(self, texture, base_width, base_height):
        self._resize_image()


    def _resize_image(self):
        stage_width, stage_height = self._stage.get_size()
        # base_width and base_height are the actual dimensions of the buffers before
        # taking the pixel aspect ratio into account. We need to get the actual
        # size of the texture to display
        frame_width, frame_height = self._video_texture.get_size()
        try:
            new_height = (frame_height * stage_width) / frame_width
        except ZeroDivisionError, e:
            print("In _resize_image: %s" % (e,))
            return
        if new_height <= stage_height:
            new_width = stage_width
            new_x = 0;
            new_y = (stage_height - new_height) / 2
        else:
            new_width  = (frame_width * stage_height) / frame_height
            new_height = stage_height
            new_x = (stage_width - new_width) / 2
            new_y = 0
        self._video_texture.set_position(new_x, new_y)
        self._video_texture.set_size(new_width, new_height)


    def _stage_key_press_event_cb(self, stage, event):
        state = event.modifier_state
        is_ctrl_pressed = (state & Clutter.ModifierType.CONTROL_MASK) != 0
        symbol = event.keyval

        if is_ctrl_pressed:
            if symbol == Clutter.KEY_q:
                self.quit()
        elif symbol == Clutter.KEY_Escape:
            self.toggle_fullscreen()
        else:
            # Each letter triggers a clip
            try:
                letter = chr(symbol)
                print("Letter %s pressed" % (letter,))
            except ValueError, e:
                pass
            else:
                if ord(letter) in range(ord('a'), ord('z')):
                    number = ord(letter) - ord('a')
                    if not self.play_clip_number(number):
                        print("No clip for letter %s" % (letter,))


    def play_clip_number(self, number=0):
        """
        Plays a clip by its index.
        """
        success = False
        try:
            filename = self._config.filenames[number]
            if os.path.exists(filename):
                self._video_texture.set_filename(filename)
                success = True
            else:
                print("No such file: %s" % (filename,))
        except IndexError, e:
            print("No clip number %d" % (number,))
        if success:
            self._current_clip_number = number
            print("Playing clip %d: %s" % (number, self._config.filenames[number]))
            self._video_texture.set_playing(True)
            if self._eos_handler_id is not None:
                print("disconnect")
                self._video_texture.disconnect(self._eos_handler_id)
            self._eos_handler_id = self._video_texture.connect("eos", self._video_texture_eos_cb)
        return success


    def toggle_fullscreen(self):
        """
        Toggles fullscreen.
        """
        if self._is_fullscreen:
            self._stage.set_fullscreen(False)
            self._is_fullscreen = False
        else:
            self._stage.set_fullscreen(True)
            self._is_fullscreen = True


if __name__ == "__main__":
    DEBUG = False
    if DEBUG:
        DEBUG_ARGS = ['--clutter-debug=all', '--cogl-debug=all']
        Clutter.init(DEBUG_ARGS)
    else:
        Clutter.init(sys.argv)

    config = Configuration()
    config.filenames = ["a.mov", "b.mov", "c.mov"]
    if len(config.filenames) == 0:
        print("You must choose at least one video file name.")
    app = Application(config)
    try:
        Clutter.main()
    except KeyboardInterrupt, e:
        pass
    sys.exit(0)

