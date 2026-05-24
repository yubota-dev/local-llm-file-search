import os
import re
import logging
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from backend.query import MediaSearchQuery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Local Media Search", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

search_engine = MediaSearchQuery()
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/search")
async def search(
    q: str = Query(...),
    top_k: int = Query(10)
):
    try:
        result = search_engine.query(q, top_k=top_k)
        candidates = result.get("candidates", [])
        return {"query": q, "results": candidates, "count": len(candidates)}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/open")
async def open_file(path: str = Query(...)):
    try:
        # スラッシュ→バックスラッシュに変換
        normalized = path.replace("/", "\\")
        file_path = Path(normalized)
        logger.info(f"Opening: {file_path}")
        if not file_path.exists():
            return JSONResponse(status_code=404, content={"error": f"Not found: {normalized}"})
        os.startfile(str(file_path))
        return {"status": "opened", "path": str(file_path)}
    except Exception as e:
        logger.error(f"Open error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/status")
async def status():
    return {
        "status": "running",
        "index_exists": Path("./data/index").exists()
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)