from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import subprocess, os, uuid, json

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
    return {"status": "Superfast Engine Active"}

# ====== 1. LIGHTNING FAST TRAILER GENERATOR (Uses Stream Copy - Takes 3 to 5 sec) ======
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
        # 1. Ultra-fast duration check using remote ffprobe
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

        # 2. Cut clips without re-encoding (-c copy) -> Instant Speed!
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

        # 3. Fast merge
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


# ====== 2. HIGH-SPEED WATERMARK (Direct Stream Pipeline) ======
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

        pos_dict = {
            "center": ("(w-text_w)/2", "(h-text_h)/2"),
            "bottom-right": ("w-text_w-30", "h-text_h-30"),
            "bottom-left": ("30", "h-text_h-30"),
            "top-right": ("w-text_w-30", "30"),
            "top-left": ("30", "30")
        }
        base_x, base_y = pos_dict.get(position, ("(w-text_w)/2", "(h-text_h)/2"))

        safe_text = text.replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:").replace("%", "\\%")
        drawtext_filter = f"drawtext=fontfile='{fontfile_path}':text='{safe_text}':fontsize={font_size}:fontcolor={font_color}:x={base_x}:y={base_y}:shadowcolor=black@0.9:shadowx=3:shadowy=3"

        # Stream directly without saving original full file to disk first
        cmd = [
            "ffmpeg", "-y",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "-i", video_url,
            "-vf", drawtext_filter,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "copy",
            out_file
        ]
        subprocess.run(cmd, check=True, timeout=180)

        return {"status": "success", "file_url": f"/videos/{job_id}.mp4"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
