from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import subprocess, os, uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("/tmp/videos", exist_ok=True)
app.mount("/videos", StaticFiles(directory="/tmp/videos"), name="videos")

@app.get("/")
def home():
    return {"status": "Superfast Watermark & Trailer Engine Active"}

# ====== 1. SUPERFAST TRAILER GENERATOR ======
@app.get("/generate-trailer")
def generate_trailer(
    video_url: str = Query(...),
    duration: int = Query(20),
    clips: int = Query(3)
):
    job_id = str(uuid.uuid4())[:8]
    out_file = f"/tmp/videos/trailer_{job_id}.mp4"
    concat_list = f"/tmp/list_{job_id}.txt"
    segment_files = []

    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            video_url
        ]
        duration_out = subprocess.check_output(probe_cmd, timeout=20).decode().strip()
        total_dur = float(duration_out) if duration_out else 60.0

        clip_len = round(duration / clips, 2)
        if clips == 2:
            points = [5, max(10, total_dur - clip_len - 5)]
        elif clips == 3:
            points = [5, total_dur / 2, max(10, total_dur - clip_len - 5)]
        elif clips == 4:
            points = [5, total_dur * 0.33, total_dur * 0.66, max(10, total_dur - clip_len - 5)]
        else:
            points = [5, total_dur * 0.25, total_dur * 0.5, total_dur * 0.75, max(10, total_dur - clip_len - 5)]

        with open(concat_list, "w") as f_list:
            for idx, st in enumerate(points):
                seg_path = f"/tmp/seg_{job_id}_{idx}.mp4"
                cut_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(st),
                    "-t", str(clip_len),
                    "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "-i", video_url,
                    "-c", "copy",
                    "-avoid_negative_ts", "make_zero",
                    seg_path
                ]
                subprocess.run(cut_cmd, check=True, timeout=30)
                segment_files.append(seg_path)
                f_list.write(f"file '{seg_path}'\n")

        merge_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            "-movflags", "+faststart",
            out_file
        ]
        subprocess.run(merge_cmd, check=True, timeout=20)

        for s in segment_files:
            if os.path.exists(s): os.remove(s)
        if os.path.exists(concat_list): os.remove(concat_list)

        return {"status": "success", "trailer_url": f"/videos/trailer_{job_id}.mp4"}

    except Exception as e:
        for s in segment_files:
            if os.path.exists(s): os.remove(s)
        if os.path.exists(concat_list): os.remove(concat_list)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ====== 2. ADVANCED WATERMARK (With All Animations & Fast Streaming) ======
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
    out_file = f"/tmp/videos/{job_id}.mp4"

    try:
        clean_color = color.replace('#', '')
        alpha_hex = format(int(opacity * 255), '02x')
        font_color = f"0x{clean_color}{alpha_hex}"

        fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if font_family == "cinematic":
            fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
        elif font_family == "digital":
            fontfile_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

        # Position Mapping
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

        safe_text = text.replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:").replace("%", "\\%")

        # Movement Formulas with Escaped Commas
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

        # Animations Handler
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
            # 1. Fixed Top
            filters.append(make_filter("(w-text_w)/2", "25"))
            # 2. Moving Diagonal
            filters.append(make_filter(diag_x, diag_y))
            # 3. Running Bottom Ticker
            filters.append(make_filter(ticker_x, ticker_y, ":box=1:boxcolor=black@0.65:boxborderw=6"))
        elif effect == "random_minute":
            filters.append(make_filter(random_x, random_y))

        combined_vf = ",".join(filters)

        cmd = [
            "ffmpeg", "-y",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "-i", video_url,
            "-vf", combined_vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28" if auto_compress else "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "copy",
            out_file
        ]
        subprocess.run(cmd, check=True, timeout=180)

        return {"status": "success", "file_url": f"/videos/{job_id}.mp4"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
