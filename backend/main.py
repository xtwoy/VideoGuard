"""Local-only FastAPI application. No queues, no web hosting, no auth by design."""
from __future__ import annotations
import hashlib
import math
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from database import get_review, save_review
from pipeline import run_live, run_demo
from report import render_html

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent/".env")
except ImportError:
    pass

MAX_UPLOAD_BYTES = 6_000_000
MAX_DURATION_SECONDS = 180
ALLOWED_SUFFIXES = {".mp4", ".mov", ".webm"}

app = FastAPI(title="VideoGuard-E",version="0.6.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET","POST"],
    allow_headers=["Content-Type"]
)

def validate_video(filename: str, content: bytes) -> str:
    """Filename, file size, and a basic container signature check."""
    name=(filename or "").replace("\\","/").split("/")[-1][:120]
    suffix=Path(name).suffix.lower()
    if not name or suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415,detail="仅支持 MP4、MOV 或 WebM 视频")
    if not content:
        raise HTTPException(status_code=400,detail="不能上传空视频")
    if len(content)>MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413,detail="演示版视频不能超过6MB")
    if suffix in (".mp4",".mov") and content[4:8]!=b"ftyp":
        raise HTTPException(status_code=422,detail="MP4/MOV文件头无效")
    if suffix==".webm" and not content.startswith(b"\x1a\x45\xdf\xa3"):
        raise HTTPException(status_code=422,detail="WebM文件头无效")
    return name

def probe_duration_ms(content: bytes, suffix: str) -> int:
    """ffprobe only checks metadata; it does NOT extract video frames or run ASR."""
    # TemporaryDirectory allows ffprobe to reopen a file on Windows too.
    with tempfile.TemporaryDirectory() as directory:
        temp=Path(directory)/("upload"+suffix)
        temp.write_bytes(content)
        try:
            p=subprocess.run(
                ["ffprobe","-v","error","-show_entries","format=duration",
                 "-of","default=nokey=1:noprint_wrappers=1",str(temp)],
                capture_output=True,text=True,timeout=10
            )
        except (OSError,subprocess.TimeoutExpired):
            raise HTTPException(status_code=422,detail="无法使用ffprobe检查视频")
    try:
        duration=float(p.stdout.strip())
        if p.returncode != 0 or not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid duration")
    except ValueError:
        raise HTTPException(status_code=422,detail="视频格式损坏或无法读取时长")
    if duration > MAX_DURATION_SECONDS:
        raise HTTPException(status_code=413,detail="演示版视频长度不能超过3分钟")
    return max(1,round(duration*1000))

@app.get("/api/health")
def health():
    return {"ok":True,"service":"VideoGuard-E","version":"0.6"}

@app.post("/api/reviews")
def create_review(
    video:UploadFile=File(...),
    title:str=Form(""),
    consent:bool=Form(False)
):
    if not consent:
        raise HTTPException(status_code=400,detail="请先确认视频素材已经授权用于审核")
    contents=video.file.read(MAX_UPLOAD_BYTES+1)
    filename=validate_video(video.filename,contents)
    duration=probe_duration_ms(contents,Path(filename).suffix.lower())
    review_id=uuid.uuid4().hex
    try:
        result=run_live(contents,duration,title[:100])
        status,error="DONE",""
    except Exception as error_obj:
        status="ERROR"
        error=("未配置阿里云百炼API环境变量"
               if "未配置阿里云" in str(error_obj)
               else "模型调用或输出解析失败，请检查API权限、额度、网络或日志")
        result={"coverage":"ERROR","observations":[],"findings":[],
                "recommendations":[],"meta":{"omni":"ERROR","jev":"NOT_RUN",
                                              "max":"NOT_RUN"}}
    record={
        "id":review_id,"video_name":filename,
        "sha256":hashlib.sha256(contents).hexdigest(),
        "duration_ms":duration,"mode":"LIVE","status":status,
        "result":result,"error":error
    }
    save_review(record)
    if status=="ERROR":
        raise HTTPException(status_code=502,detail={"review_id":review_id,"message":error})
    return get_review(review_id)

@app.post("/api/demo")
def create_demo():
    record={"id":uuid.uuid4().hex,"video_name":"合成示例｜非真实视频",
            "sha256":"demo","duration_ms":25000,"mode":"DEMO",
            "status":"DONE","result":run_demo(),"error":""}
    save_review(record)
    return get_review(record["id"])

@app.get("/api/reviews/{review_id}")
def read_review(review_id: str):
    record=get_review(review_id)
    if record is None:
        raise HTTPException(status_code=404,detail="找不到这条审核记录")
    return record

@app.get("/api/reviews/{review_id}/report",response_class=HTMLResponse)
def report(review_id: str):
    record=get_review(review_id)
    if record is None:
        raise HTTPException(status_code=404,detail="找不到这条审核记录")
    return HTMLResponse(
        render_html(record),
        headers={
            "Content-Disposition":f'attachment; filename="VideoGuard-{record["id"][:12]}.html"',
            "X-Content-Type-Options":"nosniff"
        }
    )
