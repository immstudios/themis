import os
import time
import re
import subprocess

from nxtools import *
from nxtools.media import *

from .output_profile import *

__all__ = ["extract", "transcode"]


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


def extract(parent):
    parent.set_status("Analyzing source")

    filters = []
    if parent["deinterlace"] and parent.meta["frame_rate"] >= 25:
        filters.append("idet")
    if parent["crop_detect"]:
        filters.append("cropdetect")

    cmd = [
            "ffmpeg",
            "-i", parent.input_path,
        ]

    if filters:
        cmd.extend([
            "-filter:v", ",".join(filters), "-f", "null", "-",
        ])


    result = {
            "is_interlaced" : False
        }
    last_idet = buff = ""
    at_frame = 0

    st = time.time()
    logging.debug("Executing {}".format(" ".join(cmd)))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    while True:
        ch = proc.stderr.read(1)
        if not ch:
            break
        ch = decode_if_py3(proc.stderr.read(1))

        if ch in ["\n", "\r"]:
            line = buff.strip()
            if line.startswith("frame="):
                m = re.match(r".*frame=\s*(\d+)\s*fps.*", line)
                if m:
                    at_frame = int(m.group(1))
                    parent.progress_handler(float(at_frame) / parent.meta["num_frames"] * 100)

            elif line.find("Repeated Fields") > -1:
                last_idet = line
            buff = ""
        else:
            buff += ch

    if last_idet:
        exp = r".*Repeated Fields: Neither:\s*(\d+)\s*Top:\s*(\d+)\s*Bottom:\s*(\d+).*"
        m = re.match(exp, last_idet)
        if m:
            n = int(m.group(1))
            t = int(m.group(2))
            b = int(m.group(3))
            tot = n + t + b
            if n / float(tot) < .9:
                result["is_interlaced"] = True

    if at_frame:
        result["num_frames"] = at_frame
    return result




def transcode(parent):
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

        if parent["deinterlace"] and parent.meta["is_interlaced"]:
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
    # Encode
    #

    res = ffmpeg(
            parent.input_path,
            parent.output_path,
            output_format=output_format,
        )

    if not res:
        return False

    res = ffprobe(parent.output_path)
    target_duration=int(res["streams"][0]["nb_frames"]) / float(parent["frame_rate"])
    logging.info("Computed target duration", target_duration)

    return True
