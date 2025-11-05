import os
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Song

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists and mount for static serving
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
AUDIO_DIR = os.path.join(UPLOAD_DIR, "audio")
COVER_DIR = os.path.join(UPLOAD_DIR, "covers")
for d in [UPLOAD_DIR, AUDIO_DIR, COVER_DIR]:
    os.makedirs(d, exist_ok=True)

app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")


@app.get("/")
def read_root():
    return {"message": "SanMusic backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


# Models for requests
class SongCreate(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    coverUrl: Optional[str] = None
    audioUrl: Optional[str] = None
    duration: Optional[float] = None


@app.get("/songs")
def list_songs() -> List[dict]:
    docs = get_documents("song", {})
    # Convert ObjectId to string if present
    out = []
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
        out.append(d)
    # newest first
    out.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
    return out


@app.post("/songs")
def create_song(song: SongCreate):
    # Basic validation: require either audioUrl or will be provided later by upload endpoint
    if not song.audioUrl:
        raise HTTPException(status_code=400, detail="audioUrl is required when not uploading a file.")
    new_id = create_document("song", song)
    return {"id": new_id}


@app.post("/songs/upload")
async def upload_song(
    title: str = Form(...),
    artist: str = Form(...),
    album: Optional[str] = Form(None),
    audio: UploadFile = File(...),
    cover: Optional[UploadFile] = File(None),
):
    # Save audio file
    audio_ext = os.path.splitext(audio.filename)[1]
    safe_audio_name = f"{int(datetime.utcnow().timestamp())}_{audio.filename.replace(' ', '_')}"
    audio_path = os.path.join(AUDIO_DIR, safe_audio_name)
    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    cover_url = None
    if cover is not None:
        safe_cover_name = f"{int(datetime.utcnow().timestamp())}_{cover.filename.replace(' ', '_')}"
        cover_path = os.path.join(COVER_DIR, safe_cover_name)
        with open(cover_path, "wb") as f:
            f.write(await cover.read())
        cover_url = f"/media/covers/{safe_cover_name}"

    audio_url = f"/media/audio/{safe_audio_name}"

    song_doc = Song(
        title=title,
        artist=artist,
        album=album,
        coverUrl=cover_url,
        audioUrl=audio_url,
    )
    new_id = create_document("song", song_doc)
    return {"id": new_id, "audioUrl": audio_url, "coverUrl": cover_url}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
