import os
import time

from nxtools import *

from .base_transcoder import *
#from .output_profile import *
from .process import *

__all__ = ["Themis"]



class Themis(BaseTranscoder):
    Process = ThemisProcess

    @property
    def defaults(self):
        return {
            "container"     : "mov",
            "output_dir"    : "output",

            "width"         : 1920,
            "height"        : 1080,
            "frame_rate"    : 25,
            "pixel_format"  : "yuv422p",
            "video_codec"   : "dnxhd",

            # optional

            "video_bitrate" : False,
            "qscale"        : False,
            "gop_size"      : False,
            "audio_codec"   : False,
            "audio_bitrate" : False,
            "audio_sample_rate" : 48000,

            #x264/x265 settings
            "level"         : False,
            "preset"        : False,
            "profile"       : False,

            # Helpers
            "expand_levels" : False,  # Expand tv color levels to full
            "deinterlace"   : True,   # Enable smart deinterlace (slower)
            "crop_detect"   : False,  # Enable smart crop detection (slower)
            "loudness"      : False,  # Normalize audio (LUFS)
            "logo"          : False,  # Path to logo to burn in

            "audio_mode"    : 0,
        }


    @property
    def reclock_ratio(self):
        source_fps = self.meta["frame_rate"]
        profile_fps = self.settings["frame_rate"]
        if source_fps >= profile_fps or profile_fps - source_fps > 3:
            return None
        return float(profile_fps) / source_fps


    def fail_clean_up(self):
        try:
            os.remove(self.output_path)
        except:
            pass
