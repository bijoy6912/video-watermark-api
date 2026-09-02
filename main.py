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
    font_family: str = Query("default"),
    opacity: float = Query(1.0),
    color: str = Query("FFFFFF"),
    position: str = Query("center"),
    style: str = Query("shadow"),
    effect: str = Query("static"),
    auto_compress: bool = Query(False)
):
    job_id = str(uuid.uuid4())[:8]
    in_file = f"/tmp/input_{job_id}.mp4"
    out_file = f"/tmp/output_{job_id}.mp4"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(video_url, headers=headers, stream=True, timeout=600)
        with open(in_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=2*1024*1024):
                if chunk:
                    f.write(chunk)

        if not text:
            return FileResponse(in_file, media_type="video/mp4", filename=f"video_{job_id}.mp4")

        # Color & Opacity
        clean_color = color.replace('#', '')
        alpha_hex = format(int(opacity * 255), '02x')
        font_color = f"0x{clean_color}{alpha_hex}"

        # Fonts
        fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if font_family == "cinematic":
            fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
        elif font_family == "digital":
            fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

        # Position mapping
        pos_dict = {
            "center": ("(w-text_w)/2", "(h-text_h)/2"),
            "bottom-right": ("w-text_w-30", "h-text_h-30"),
            "bottom-left": ("30", "h-text_h-30"),
            "top-right": ("w-text_w-30", "30"),
            "top-left": ("30", "30")
        }
        base_x, base_y = pos_dict.get(position, ("(w-text_w)/2", "(h-text_h)/2"))

        # Styles (Shadow, Outlines, Boxes, Neon)
        style_opts = ""
        if style == "shadow":
            style_opts = ":shadowcolor=black@0.9:shadowx=3:shadowy=3"
        elif style == "outline":
            style_opts = ":bordercolor=black:borderw=3"
        elif style == "outline_white":
            style_opts = ":bordercolor=white:borderw=3"
        elif style == "box_black":
            style_opts = ":box=1:boxcolor=black@0.75:boxborderw=8"
        elif style == "box_red":
            style_opts = ":box=1:boxcolor=red@0.75:boxborderw=8"
        elif style == "neon":
            style_opts = ":shadowcolor=cyan@0.8:shadowx=0:shadowy=0:bordercolor=cyan:borderw=2"

        safe_text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")

        # Movement Expressions
        ticker_x = "w-mod(t*160\\,w+text_w)"
        ticker_y = "h-text_h-20"
        diag_x = "w-text_w-mod(t*55\\,w)"
        diag_y = "h-text_h-mod(t*35\\,h)"
        random_x = "if(mod(floor(t/60)\\,2)\\,30\\,w-text_w-30)"
        random_y = "if(mod(floor(t/120)\\,2)\\,30\\,h-text_h-30)"

        filters = []
        def make_filter(x, y, custom_style=None):
            st = custom_style if custom_style is not None else style_opts
            return f"drawtext=fontfile='{fontfile_path}':text='{safe_text}':fontsize={font_size}:fontcolor={font_color}:x={x}:y={y}{st}"

        # Exact Effects implementation
        if effect == "static":
            filters.append(make_filter(base_x, base_y))
        elif effect == "ticker":
            filters.append(make_filter(ticker_x, ticker_y, ":box=1:boxcolor=black@0.65:boxborderw=6"))
        elif effect == "diagonal":
            filters.append(make_filter(diag_x, diag_y))
        elif effect == "static_ticker":
            filters.append(make_filter(base_x, base_y))
            filters.append(make_filter(ticker_x, ticker_y, ":box=1:boxcolor=black@0.65:boxborderw=6"))
        elif effect == "diagonal_ticker":
            filters.append(make_filter(diag_x, diag_y))
            filters.append(make_filter(ticker_x, ticker_y, ":box=1:boxcolor=black@0.65:boxborderw=6"))
        elif effect == "static_diagonal_ticker":
            # 1. Top Fixed
            filters.append(make_filter("(w-text_w)/2", "25"))
            # 2. Diagonal Floating
            filters.append(make_filter(diag_x, diag_y))
            # 3. Running Bottom Ticker
            filters.append(make_filter(ticker_x, ticker_y, ":box=1:boxcolor=black@0.65:boxborderw=6"))
        elif effect == "random_minute":
            filters.append(make_filter(random_x, random_y))

        combined_vf = ",".join(filters)

        encoding_opts = [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "28" if auto_compress else "22",
            "-c:a", "copy"
        ]

        cmd = ["ffmpeg", "-y", "-i", in_file, "-vf", combined_vf] + encoding_opts + [out_file]
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
