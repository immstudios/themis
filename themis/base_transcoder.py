from __future__ import print_function

import os
import time

from nxtools import *
from nxtools.media import *

from .probe import *

__all__ = ["BaseTranscoder"]

class BaseTranscoder(object):
    def __init__(self, input_path, **kwargs):
        self.input_path = str(input_path)
        self.settings = self.defaults
        self.settings.update(kwargs)
        self.meta = probe(self.input_path)
        self.last_progress_time = time.time()
        self.aborted = False
        if self.meta:
            self.is_ok = True
        else:
            self.set_status("Unable to open file", level="error")
            self.is_ok = False

    #
    # Settings
    #

    @property
    def defaults(self):
        return {}

    def __getitem__(self, key):
        return self.settings[key]

    def __setitem__(self, key, value):
        self.settings[key] = value

    def __len__(self):
        return self.is_ok

    #
    # Source metadata helpers
    #

    @property
    def audio_tracks(self):
        return self.meta.get("audio_tracks", [])

    @property
    def mark_in(self):
        return self.settings.get("mark_in", 0)

    @property
    def mark_out(self):
        return self.settings.get("mark_out", 0)

    @property
    def duration(self):
        return (self.mark_out or self.meta["duration"]) - self.mark_in

    @property
    def has_video(self):
        return self.meta["video_index"] >= 0

    #
    # Paths and names
    #

    @property
    def container(self):
        return os.path.splitext(self.input_path)[1].lstrip(".")

    @property
    def base_name(self):
        return self.settings.get("base_name", False) or get_base_name(self.input_path)

    @property
    def friendly_name(self):
        return self.settings.get("friendly_name", False) or self.base_name

    @property
    def profile_name(self):
        return self.settings.get("profile_name", self.settings["video_bitrate"])

    @property
    def output_dir(self):
        output_path = self.output_path
        if not output_path:
            return False
        return os.path.split(output_path)[0]

    @property
    def output_path(self):
        if "output_path" in self.settings:
            return self.settings["output_path"]
        if "output_dir" in self.settings:
            return os.path.join(
                    self.settings["output_dir"],
                    "{}.{}".format( self.base_name, self.settings["container"])
                )
        return False

    #
    # Processing
    #

    def set_status(self, message, level="debug"):
        self.status = message
        {
            False : lambda x: x,
            "debug"     : logging.debug,
            "info"      : logging.info,
            "warning"   : logging.warning,
            "error"     : logging.error,
            "good_news" : logging.goodnews
        }.get(level, False)("{}: {}".format(self.friendly_name, message))

    def progress_handler(self, progress):
        if time.time() - self.last_progress_time > 3:
            logging.debug("{}: {} ({:.02f}% done)".format(
                    self.friendly_name,
                    self.status,
                    progress
                ))
            self.last_progress_time = time.time()

    def start(self, **kwargs):
        if not self.output_path:
            self.set_status("Failed. No output specified", level="error")
            return False

        output_dir = self.output_dir
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception:
                log_traceback()
                self.set_status("Failed. Unable to create output directory {}".format(output_dir))
                return False

        start_time = time.time()
        self.settings.update(kwargs)
        self.set_status(
                "Starting {} transcoder".format(self.__class__.__name__),
                level="info"
            )

        try:
            self.process = self.Process(self)
            result = self.process.start()
        except Exception:
            log_traceback("Unhandled exception occured during transcoding")
            result = False

        if self.aborted:
            return True

        if not result:
            self.fail_clean_up()
            self.set_status("Failed", level="error")
            return False

        self.clean_up()

        # Final report
        end_time = time.time()
        proc_time = end_time - start_time
        speed = self.duration / proc_time
        self.set_status(
                "Completed in {} ({:.2f}x real time)".format(proc_time, speed),
                level="good_news"
            )
        return True

    def abort(self):
        if self.process:
            self.process.abort()
        self.fail_clean_up()
        self.set_status("Aborted", level="warning")
        self.aborted = True

    #
    # Clean-up
    #

    def clean_up(self):
        pass

    def fail_clean_up(self):
        pass
