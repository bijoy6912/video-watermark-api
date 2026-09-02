from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    return {"status": "Video & Trailer Engine is Live!"}

# ====== 1. TRAILER GENERATOR API ======
@app.get("/generate-trailer")
def generate_trailer(
    video_url: str = Query(...),
    duration: int = Query(20),
    clips: int = Query(3)
):
    job_id = str(uuid.uuid4())[:8]
    out_file = f"/tmp/videos/trailer_{job_id}.mp4"

    try:
        # 1. Get video total duration using ffprobe
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "-headers", "User-Agent: Mozilla/5.0\r\n",
            video_url
        ]
        total_duration_str = subprocess.check_output(probe_cmd, timeout=30).decode().strip()
        total_duration = float(total_duration_str)

        # 2. Calculate clip segments
        clip_len = duration / clips
        segment_files = []

        if clips == 2:
            start_points = [5, max(0, total_duration - clip_len - 5)]
        elif clips == 3:
            start_points = [5, total_duration / 2, max(0, total_duration - clip_len - 5)]
        elif clips == 4:
            start_points = [5, total_duration * 0.33, total_duration * 0.66, max(0, total_duration - clip_len - 5)]
        else: # 5 clips
            start_points = [5, total_duration * 0.25, total_duration * 0.50, total_duration * 0.75, max(0, total_duration - clip_len - 5)]

        concat_list_path = f"/tmp/list_{job_id}.txt"
        with open(concat_list_path, "w") as f_list:
            for idx, st in enumerate(start_points):
                seg_path = f"/tmp/seg_{job_id}_{idx}.mp4"
                cut_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(st),
                    "-t", str(clip_len),
                    "-headers", "User-Agent: Mozilla/5.0\r\n",
                    "-i", video_url,
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    seg_path
                ]
                subprocess.run(cut_cmd, check=True)
                segment_files.append(seg_path)
                f_list.write(f"file '{seg_path}'\n")

        # 3. Concatenate all cut segments together
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            "-movflags", "+faststart",
            out_file
        ]
        subprocess.run(concat_cmd, check=True)

        # Clean up temporary segments
        for s in segment_files:
            if os.path.exists(s): os.remove(s)
        if os.path.exists(concat_list_path): os.remove(concat_list_path)

        return {"status": "success", "trailer_url": f"/videos/trailer_{job_id}.mp4"}

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ====== 2. WATERMARK PROCESSOR API ======
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
    out_file = f"/tmp/videos/{job_id}.mp4"

    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(video_url, headers=headers, stream=True, timeout=300)
        with open(in_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=2*1024*1024):
                if chunk: f.write(chunk)

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

        safe_text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")
        drawtext_filter = f"drawtext=fontfile='{fontfile_path}':text='{safe_text}':fontsize={font_size}:fontcolor={font_color}:x={base_x}:y={base_y}:shadowcolor=black@0.9:shadowx=3:shadowy=3"

        cmd = [
            "ffmpeg", "-y", "-i", in_file,
            "-vf", drawtext_filter,
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-c:a", "copy", out_file
        ]
        subprocess.run(cmd, check=True)
        if os.path.exists(in_file): os.remove(in_file)

        return {"status": "success", "file_url": f"/videos/{job_id}.mp4"}
    except Exception as e:
        if os.path.exists(in_file): os.remove(in_file)
        return JSONResponse(status_code=500, content={"error": str(e)})
