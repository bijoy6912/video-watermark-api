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
        # 1. Download source video with headers to avoid anti-bot blocks
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(video_url, headers=headers, stream=True, timeout=600)
        with open(in_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=2*1024*1024):
                if chunk:
                    f.write(chunk)

        if not text:
            return FileResponse(in_file, media_type="video/mp4", filename=f"video_{job_id}.mp4")

        # 2. Color & Opacity
        clean_color = color.replace('#', '')
        font_color = f"0x{clean_color}@{opacity}"

        # 3. Position & Motion Logic (Safe Math Expressions without nested quotes)
        if motion == "bottom_ticker":
            x_expr = "w-mod(t*160,w+text_w)"
            y_expr = "h-text_h-20"
        elif motion == "diagonal_move":
            x_expr = "w-text_w-mod(t*50,w)"
            y_expr = "h-text_h-mod(t*35,h)"
        elif motion == "random":
            # Swaps position safely every 6 seconds
            x_expr = "if(eq(mod(floor(t/6),2),0),40,w-text_w-40)"
            y_expr = "if(eq(mod(floor(t/12),2),0),40,h-text_h-40)"
        else:
            # Static Positions
            pos_dict = {
                "center": ("(w-text_w)/2", "(h-text_h)/2"),
                "south_east": ("w-text_w-30", "h-text_h-30"),
                "south_west": ("30", "h-text_h-30"),
                "north_east": ("w-text_w-30", "30"),
                "north_west": ("30", "30"),
                "north": ("(w-text_w)/2", "30"),
                "south": ("(w-text_w)/2", "h-text_h-30")
            }
            x_expr, y_expr = pos_dict.get(position, ("(w-text_w)/2", "(h-text_h)/2"))

        # 4. Style Logic
        style_parts = []
        if style == "shadow":
            style_parts = ["shadowcolor=black@0.9", "shadowx=3", "shadowy=3"]
        elif style == "outline":
            style_parts = ["bordercolor=black", "borderw=3"]
        elif style == "box_dark":
            style_parts = ["box=1", "boxcolor=black@0.65", "boxborderw=8"]
        elif style == "box_light":
            style_parts = ["box=1", "boxcolor=white@0.8", "boxborderw=8"]

        # Safe text escaping for FFmpeg drawtext
        escaped_text = text.replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:").replace("%", "\\%")

        # Filter string assembly
        filter_params = [
            f"text='{escaped_text}'",
            f"fontsize={font_size}",
            f"fontcolor={font_color}",
            f"x={x_expr}",
            f"y={y_expr}"
        ] + style_parts

        drawtext_filter = "drawtext=" + ":".join(filter_params)

        # 5. Fast Encoding & Pixel Format Settings
        encoding_opts = [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "28" if auto_compress else "22",
            "-c:a", "copy"
        ]

        cmd = ["ffmpeg", "-y", "-i", in_file, "-vf", drawtext_filter] + encoding_opts + [out_file]
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
