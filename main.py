from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import subprocess, os, uuid, requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "Video Watermark Server is Running!"}

@app.get("/process")
def process_video(
    video_url: str = Query(...),
    text: str = Query(""),
    font_size: int = Query(26),
    font_family: str = Query("Default Sans"),
    opacity: float = Query(1.0),
    color: str = Query("FFFFFF"),
    position: str = Query("center"),
    style: str = Query("shadow"),
    motion: str = Query("static"),
    auto_compress: bool = Query(False)
):
    job_id = str(uuid.uuid4())[:8]
    in_file = f"/tmp/input_{job_id}.mp4"
    out_file = f"/tmp/output_{job_id}.mp4"

    try:
        # Download source video
        r = requests.get(video_url, stream=True, timeout=600)
        with open(in_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=2*1024*1024):
                if chunk:
                    f.write(chunk)

        if not text:
            # If no watermark text provided, return original
            return FileResponse(in_file, media_type="video/mp4", filename=f"video_{job_id}.mp4")

        # Color & Opacity
        alpha_hex = hex(int(opacity * 255))[2:].zfill(2)
        font_color = f"0x{color}{alpha_hex}"

        # Font mapping
        font_file_arg = ""
        if font_family == "Bold Heavy":
            font_file_arg = ":font='DejaVu Sans':fontweight=bold"
        elif font_family == "Cinematic Serif":
            font_file_arg = ":font='DejaVu Serif'"
        elif font_family == "Digital LED":
            font_file_arg = ":font='DejaVu Sans Mono'"

        # Base Position Coords
        pos_coords = {
            "center": "x=(w-text_w)/2:y=(h-text_h)/2",
            "south_east": "x=w-text_w-30:y=h-text_h-30",
            "south_west": "x=30:y=h-text_h-30",
            "north_east": "x=w-text_w-30:y=30",
            "north_west": "x=30:y=30",
            "north": "x=(w-text_w)/2:y=30",
            "south": "x=(w-text_w)/2:y=h-text_h-30"
        }
        xy_str = pos_coords.get(position, "x=(w-text_w)/2:y=(h-text_h)/2")

        # Motion & Animation handling
        if motion == "bottom_ticker":
            xy_str = "x=w-mod(t*180\\,w+text_w):y=h-text_h-18"
        elif motion == "diagonal_move":
            xy_str = "x=w-text_w-mod(t*45\\,w):y=h-text_h-mod(t*30\\,h)"
        elif motion == "random":
            xy_str = "x='if(eq(mod(floor(t/5),2),0),30,w-text_w-30)':y='if(eq(mod(floor(t/10),2),0),30,h-text_h-30)'"

        # Style / Outline / Box handling
        style_args = ""
        if style == "shadow":
            style_args = ":shadowcolor=black@0.9:shadowx=3:shadowy=3"
        elif style == "outline":
            style_args = ":bordercolor=black:borderw=3"
        elif style == "box_dark":
            style_args = ":box=1:boxcolor=black@0.65:boxborderw=8"
        elif style == "box_light":
            style_args = ":box=1:boxcolor=white@0.8:boxborderw=8"

        # Safe string formatting for FFmpeg
        safe_text = text.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")

        drawtext_filter = f"drawtext=text='{safe_text}':fontsize={font_size}:fontcolor={font_color}{font_file_arg}:{xy_str}{style_args}"

        # Video compression option
        encoding_args = ["-c:v", "libx264", "-crf", "28", "-preset", "faster"] if auto_compress else ["-c:v", "libx264", "-crf", "22", "-preset", "veryfast"]

        cmd = ["ffmpeg", "-y", "-i", in_file, "-vf", drawtext_filter] + encoding_args + ["-c:a", "copy", out_file]
        subprocess.run(cmd, check=True)

        if os.path.exists(in_file):
            os.remove(in_file)

        return FileResponse(out_file, media_type="video/mp4", filename=f"watermarked_{job_id}.mp4")

    except Exception as e:
        if os.path.exists(in_file):
            os.remove(in_file)
        if os.path.exists(out_file):
            os.remove(out_file)
        return {"error": str(e)}
