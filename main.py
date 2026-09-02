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
    text: str = Query("Watermark"),
    font_size: int = Query(32),
    position: str = Query("south_east")
):
    job_id = str(uuid.uuid4())[:8]
    in_file = f"/tmp/input_{job_id}.mp4"
    out_file = f"/tmp/output_{job_id}.mp4"

    try:
        r = requests.get(video_url, stream=True, timeout=600)
        with open(in_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=2*1024*1024):
                if chunk:
                    f.write(chunk)

        pos_map = {
            "center": "(w-text_w)/2:(h-text_h)/2",
            "south_east": "w-text_w-30:h-text_h-30",
            "south_west": "30:h-text_h-30",
            "north_east": "w-text_w-30:30",
            "north_west": "30:30"
        }
        xy = pos_map.get(position, "w-text_w-30:h-text_h-30")

        cmd = [
            "ffmpeg", "-y", "-i", in_file,
            "-vf", f"drawtext=text='{text}':fontsize={font_size}:fontcolor=white:x={xy}:box=1:boxcolor=black@0.5:boxborderw=6",
            "-c:a", "copy", out_file
        ]
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
