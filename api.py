from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

from .converter import convert_to_mpp
from .mpp_writer import MPPUnavailable
from .parsers import parse_file

app = FastAPI(title="Persian Document → Microsoft Project", version="1.0.0")

ALLOWED = {".pdf", ".doc", ".docx"}
MAX_BYTES = 50 * 1024 * 1024

HTML = r"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>تبدیل PDF / Word به MPP</title>
<style>
body{font-family:Tahoma,Arial,sans-serif;background:#f4f6f8;margin:0;color:#17202a}.wrap{max-width:960px;margin:45px auto;padding:0 20px}.card{background:#fff;border-radius:18px;padding:28px;box-shadow:0 12px 40px rgba(0,0,0,.08)}
h1{margin-top:0}.drop{border:2px dashed #7d8b99;border-radius:14px;padding:38px;text-align:center;background:#fbfcfd}.row{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}.field{flex:1;min-width:220px}input[type=text],input[type=file]{width:100%;box-sizing:border-box;padding:12px;border:1px solid #ccd3da;border-radius:10px}button{padding:12px 18px;border:0;border-radius:10px;background:#1f6feb;color:#fff;font-weight:700;cursor:pointer}button:disabled{opacity:.5}.meta{margin-top:20px;padding:15px;border-radius:10px;background:#f6f8fa;white-space:pre-wrap}.err{color:#b42318}.ok{color:#067647}
</style></head><body><div class="wrap"><div class="card"><h1>تبدیل سند فارسی به Microsoft Project</h1>
<p>فایل PDF یا Word را انتخاب کنید. سیستم تلاش می‌کند WBS، فعالیت‌ها، مدت، تاریخ و پیش‌نیازها را استخراج کند و فایل باینری واقعی <b>.mpp</b> بسازد.</p>
<form id="f"><div class="drop"><input id="file" type="file" accept=".pdf,.doc,.docx" required></div>
<div class="row"><div class="field"><label>نام پروژه (اختیاری)</label><input id="name" type="text" placeholder="مثلاً پروژه پیاده‌سازی شبکه"></div></div>
<div class="row"><button id="btn" type="submit">تبدیل به MPP</button></div></form><div id="status" class="meta">آماده.</div></div></div>
<script>
const f=document.getElementById('f'), st=document.getElementById('status'), btn=document.getElementById('btn');
f.addEventListener('submit', async e=>{e.preventDefault(); const file=document.getElementById('file').files[0]; if(!file)return; btn.disabled=true; st.textContent='در حال پردازش...';
const fd=new FormData(); fd.append('file',file); fd.append('project_name',document.getElementById('name').value);
try{const r=await fetch('/convert',{method:'POST',body:fd}); if(!r.ok){let d='خطا'; try{d=(await r.json()).detail||d}catch{} throw new Error(d)} const blob=await r.blob(); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=file.name.replace(/\.[^.]+$/,'')+'.mpp'; a.click(); URL.revokeObjectURL(url); st.className='meta ok'; st.textContent='تبدیل با موفقیت انجام شد و فایل MPP دانلود شد.'}catch(err){st.className='meta err'; st.textContent='خطا: '+err.message}finally{btn.disabled=false}});
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML


@app.get("/health")
def health():
    return {"status": "ok", "native_mpp": __import__("platform").system() == "Windows"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "فقط PDF، DOC و DOCX پشتیبانی می‌شود.")
    with tempfile.TemporaryDirectory(prefix="persian_mpp_analyze_") as td:
        src = Path(td) / (Path(file.filename or "input").name)
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "حجم فایل بیشتر از 50MB است.")
        src.write_bytes(data)
        try:
            project = parse_file(src)
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"project": project.name, "task_count": len(project.tasks), "tasks": [
            {"name": t.name, "level": t.level, "duration_days": t.duration_days,
             "start": t.start.isoformat() if t.start else None,
             "finish": t.finish.isoformat() if t.finish else None,
             "predecessors": [{"task": d.predecessor, "type": d.link, "lag_days": d.lag_days} for d in t.predecessors],
             "resources": t.resource_names, "notes": t.notes, "source_line": t.source_line, "source_table": t.source_table}
            for t in project.tasks
        ]}


@app.post("/convert")
async def convert(file: UploadFile = File(...), project_name: str = Form("")):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(400, "فقط PDF، DOC و DOCX پشتیبانی می‌شود.")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "حجم فایل بیشتر از 50MB است.")
    temp_dir = tempfile.TemporaryDirectory(prefix="persian_mpp_")
    src = Path(temp_dir.name) / Path(file.filename or "input").name
    src.write_bytes(data)
    try:
        out = Path(temp_dir.name) / f"{src.stem}.mpp"
        result = convert_to_mpp(src, out, project_name=project_name or None)
        if not result.native_mpp:
            raise HTTPException(503, "Microsoft Project برای تولید MPP در دسترس نیست.")
        # Keep temp directory alive for FileResponse lifetime by attaching it to response closure is awkward;
        # copy to a persistent temp path instead.
        persistent = Path(tempfile.gettempdir()) / f"persian-mpp-{uuid.uuid4().hex}.mpp"
        persistent.write_bytes(result.output.read_bytes())
        return FileResponse(
            persistent, media_type="application/octet-stream",
            filename=f"{src.stem}.mpp",
            background=BackgroundTask(lambda: persistent.unlink(missing_ok=True)),
        )
    except MPPUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        temp_dir.cleanup()
