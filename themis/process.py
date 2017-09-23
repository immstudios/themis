import os
import time
import re
import subprocess
import signal

from nxtools import *
from nxtools.media import *

from .output_profile import *

__all__ = ["ThemisProcess"]

enable_ffmpeg_debug()


def themis_arc(w, h, sw, sh, aspect, **kwargs):
    taspect = float(w) / h
    if abs(taspect - aspect) < 0.01:
        if sw == w and sh == h:
            return []
        return ["scale={}:{}".format(w,h)]
    if taspect > aspect: # pillarbox
        pt = 0
        ph = h
        pw = int (h*aspect)
        pl = int((w - pw)/2.0)
    else: # letterbox
        pl = 0
        pw = w
        ph = int(w * (1/aspect))
        pt = int((h - ph)/2.0)
    return [
            "scale={}:{}".format(pw, ph),
            "pad={}:{}:{}:{}:black".format(w,h,pl,pt)
        ]




class ThemisProcess(object):
    def __init__(self, parent):
        self.parent = parent
        self.on_abort = None

    def start(self):
        parent = self.parent

        # Detailed source analysis
        # TODO: Use only if needed

        parent.set_status("Analyzing")

        analyser = FFAnalyse(parent.input_path)
        self.on_abort = analyser.stop
        new_meta = analyser.work()
        self.on_abort = False
        if not new_meta:
            return False
        parent.meta.update(new_meta)

        #
        #
        #

        tempo = parent.reclock_ratio
        source_duration = parent.meta["num_frames"] / float(parent.meta["frame_rate"])
        target_duration = source_duration * tempo if tempo else source_duration

        input_format = []
        output_format = []

        #
        # Video settings
        #

        vfilters = []
        if parent.has_video:
            output_format.append(
                    ["map", "0:{}".format(parent.meta["video_index"])]
                )

            if tempo:
                vfilters.append("setpts={}*PTS".format(1/tempo))

            if parent["deinterlace"] and parent.meta.get("is_interlaced", False):
                vfilters.append(filter_deinterlace())

            vfilters.extend(
                themis_arc(
                        parent["width"],
                        parent["height"],
                        parent.meta["width"],
                        parent.meta["height"],
                        parent.meta["aspect_ratio"]
                    )
                )

        else:
            pass # TODO: create black video

        if vfilters:
            output_format.append(["filter:v", join_filters(*vfilters)])
        output_format.extend(get_video_profile(**parent.settings))

        #
        # Audio modes:
        #
        #  0: No change
        #  1: One stereo pair
        #  2: Multiple stereo tracks
        #  3: Stereo pairs in one track
        #

        audio_mode = 0
        if audio_mode < 3:
            for i, track in enumerate(parent.audio_tracks):
                afilters = ["rubberband=tempo={}".format(tempo)] if tempo else []
                afilters.append("apad")
                afilters.append("atrim=duration={}".format(target_duration))

                output_format.extend([
                        ["map", "0:{}".format(track.id)],
                        ["filter:a", join_filters(*afilters)]
                    ])

                if audio_mode in [1,2]:
                    output_format.append(["ac", 2])

                output_format.extend(get_audio_profile(**parent.settings))

                if audio_mode == 1:
                    break

        elif audio_mode == 3:
            logging.warning("channel muxing is not currently supported")
            pass

        #
        # Container settings
        #

        output_format.extend(get_container_profile(**parent.settings))

        #
        # Transcode
        #

        parent.set_status("Transcoding")
        ff = FFMPEG(
                parent.input_path,
                parent.output_path,
                output_format=output_format
            )
        self.on_abort = ff.stop
        ff.start()
        ff.wait(parent.progress_handler)

        return not bool(ff.return_code)


    def abort(self):
        if self.on_abort:
            self.on_abort()
