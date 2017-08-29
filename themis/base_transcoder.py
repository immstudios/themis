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
        if self.meta:
            self.is_ok = True
        else:
            self.set_status("Unable to open file", level="error")
            self.is_ok = False

    def __getitem__(self, key):
        return self.settings[key]

    def __len__(self):
        return self.is_ok

    @property
    def defaults(self):
        return {}

    # Clean-up

    def clean_up(self):
        pass

    def fail_clean_up(self):
        self.clean_up()

    # Source metadata

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

    # Paths and names

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
    def output_path(self):
        if "output_path" in self.settings:
            return self.settings["output_path"]
        if "output_dir" in self.settings:
            return os.path.join(
                self.settings["output_dir"], "{}.{}".format(
                        self.settings["output_dir"],
                        self.settings["container"]
                    )
                )

    # Processing

    def set_status(self, message, level="debug"):
        self.status = message
        {
            False : lambda x: x,
            "debug" : logging.debug,
            "info" : logging.info,
            "warning" : logging.warning,
            "error" : logging.error,
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


    def process(self):
        logging.warning("Nothing to do. You must override process method")


    def start(self, **kwargs):
        self.set_status("Starting {} transcoder".format(self.__class__.__name__), level="info")
        start_time = time.time()
        self.settings.update(kwargs)
        try:
            result = self.process()

        except KeyboardInterrupt:
            print ()
            self.set_status("Aborted", level="warning")
            self.fail_clean_up()
            raise KeyboardInterrupt

        except Exception:
            log_traceback("Unhandled exception occured during transcoding")
            result = False

        if not result:
            self.fail_clean_up()
            self.set_status("Failed", level="error")
            return False

        # Final report

        end_time = time.time()
        proc_time = end_time - start_time
        speed = self.duration / proc_time
        logging.info(
            "{}: transcoding {:.2f}s long video finished in {} ({:.2f}x realtime)".format(
                self.friendly_name,
                self.duration,
                s2words(proc_time),
                speed
                ),
            )
        self.set_status("Completed", level="good_news")
        return True
