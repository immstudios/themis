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
    """
    This function:
        - extracts audio tracks
        - detects crop
        - detects interlaced content

    It does not:
        - analyze loudness (audio tracks may be time-stretched later)
    """

    parent.set_status("Extracting tracks")

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
            "-map", "0:{}".format(parent.meta["video_index"]),
            "-filter:v", ",".join(filters), "-f", "null", "-",
        ])

    for i, track in enumerate(parent.audio_tracks):
        track.source_audio_path = track.final_audio_path = get_temp("wav")
        cmd.extend(["-map", "0:{}".format(track.id)])
        cmd.extend(["-c:a", "pcm_s16le"])
        if parent["to_stereo"]:
            cmd.extend(["-ac", "2"])
        cmd.append(track.source_audio_path)


    result = {
            "is_interlaced" : False
        }
    last_idet = buff = ""
    at_frame = 0

    st = time.time()
    logging.debug("Executing: {}".format(" ".join(cmd)))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    while proc.poll() == None:
        try:
            ch = decode_if_py3(proc.stderr.read(1))
        except:
            continue
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
    source_duration = target_duration = parent.meta["num_frames"] / float(parent.meta["frame_rate"])

    tempo = parent.reclock_ratio
    if tempo:
        target_duration = source_duration * tempo


    logging.info("Expected target duration", target_duration)

    input_format = []
    output_format = []
    vfilters = []
    afilters = []


    afilters.append("apad")
    afilters.append("atrim=duration={}".format(source_duration))

    if tempo:
        vfilters.append("setpts={}*PTS".format(1/tempo))
        afilters.append("rubberband=tempo={}".format(tempo))
#        afilters.append("apad")


#    if parent["deinterlace"] and parent.meta["is_interlaced"]:
#        logging.debug("{}: Using deinterlace filter".format(parent.friendly_name))
#        vfilters.append(filter_deinterlace())


    vfilters.extend(
        themis_arc(
                parent["width"],
                parent["height"],
                parent.meta["width"],
                parent.meta["height"],
                parent.meta["aspect_ratio"]
            )
        )

    if vfilters:
        output_format.append(["filter:v", join_filters(*vfilters)])
    if afilters:
        output_format.append(["filter:a", join_filters(*afilters)])


    #temp_path = get_temp(parent["container"])


    output_format.extend(get_output_profile(**parent.settings))
    ffmpeg(
            parent.input_path,
            parent.output_path,
#            temp_path,
            output_format=output_format,
            #stderr=None
        )

    res = ffprobe(parent.output_path)
    target_duration=int(res["streams"][0]["nb_frames"]) / float(parent["frame_rate"])
    logging.info("Computed target duration", target_duration)

    return True

    #
    # second pass
    #

#    res = ffprobe(temp_path)
#    target_duration=int(res["streams"][0]["nb_frames"]) / float(parent["frame_rate"])
#
#    second_pass_format = [
#            ["c:v", "copy"],
#            ["filter:a", "apad"],
#            ["t", target_duration]
#        ]
#    second_pass_format.extend(get_audio_encoding_settings(**parent.settings))
#
#    ffmpeg(
#            temp_path,
#            parent.output_path,
#            output_format=second_pass_format
#        )
#    os.remove(temp_path)


    return True
