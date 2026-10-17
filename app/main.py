import os, json, uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, List, Literal
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb
from .measurement import calculate, segment_garment, FIELDS, mae

ROOT=Path(__file__).resolve().parent.parent
load_dotenv(ROOT/'.env')
DB=os.getenv('DATABASE_URL','')

def db():
    if not DB: raise HTTPException(503,'DATABASE_URL missing; see README')
    return psycopg.connect(DB)

app=FastAPI(title='Garment Vision: Calibrated Measurement')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

@app.get('/')
def index(): return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/health')
def health(): return {'status':'ok','database_configured':bool(DB)}

@app.post('/api/contour')
async def contour(file:UploadFile=File(...)):
    if file.content_type not in ('image/jpeg','image/png','image/webp'): raise HTTPException(415,'JPEG, PNG or WebP only')
    data=await file.read(12*1024*1024+1)
    if len(data)>12*1024*1024: raise HTTPException(413,'Maximum file size 12 MB')
    try: return segment_garment(data)
    except ValueError as exc: raise HTTPException(422,str(exc))

class Point(BaseModel):
    x:float=Field(ge=0); y:float=Field(ge=0)

class Segment(BaseModel):
    a:Point; b:Point

class Submission(BaseModel):
    garment_name:str=Field(min_length=1,max_length=120)
    garment_type:Literal['tshirt','jeans']
    image_filename:str=Field(default='',max_length=255)
    image_width:int=Field(ge=1,le=10000)
    image_height:int=Field(ge=1,le=10000)
    reference_cm:float=Field(gt=0,le=100)
    reference:Segment
    segments:Dict[str,Segment]
    manual_truth_cm:Dict[str,float]|None=None
    @model_validator(mode='after')
    def validate_points(self):
        if set(self.segments)!=set(FIELDS[self.garment_type]): raise ValueError('Exactly the expected measurement names are required')
        for s in [self.reference,*self.segments.values()]:
            for p in (s.a,s.b):
                if p.x>self.image_width or p.y>self.image_height: raise ValueError('Point outside image')
        if self.manual_truth_cm is not None:
            if set(self.manual_truth_cm)!=set(FIELDS[self.garment_type]) or any(v<=0 or v>250 for v in self.manual_truth_cm.values()): raise ValueError('Invalid manual truth')
        return self

@app.post('/api/measurements')
def save(body:Submission):
    points=lambda s:((s.a.x,s.a.y),(s.b.x,s.b.y))
    try: result=calculate(points(body.reference),body.reference_cm,{k:points(v) for k,v in body.segments.items()})
    except ValueError as exc: raise HTTPException(422,str(exc))
    report=mae(result['measurements_cm'],body.manual_truth_cm) if body.manual_truth_cm else None
    record_id=str(uuid.uuid4())
    try:
        with db() as con:
            with con.cursor() as cur:
                cur.execute('''INSERT INTO garment_measurements_v2 (id,garment_name,garment_type,image_filename,image_width,image_height,reference_cm,calibration_pixels,measurements_cm,manual_truth_cm,validation_report,point_data) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (record_id,body.garment_name,body.garment_type,body.image_filename,body.image_width,body.image_height,body.reference_cm,result['calibration_pixels'],Jsonb(result['measurements_cm']),Jsonb(body.manual_truth_cm) if body.manual_truth_cm else None,Jsonb(report) if report else None,Jsonb(body.model_dump())))
    except psycopg.Error as exc: raise HTTPException(503,'Database unavailable or schema not installed. Run schema.sql') from exc
    return {'id':record_id,**result,'validation':report}

@app.get('/api/records')
def records():
    try:
        with db() as con:
            with con.cursor() as cur:
                cur.execute('SELECT id::text,garment_name,garment_type,measurements_cm,validation_report,created_at FROM garment_measurements_v2 ORDER BY created_at DESC LIMIT 100')
                return [{'id':r[0],'name':r[1],'type':r[2],'measurements_cm':r[3],'validation':r[4],'created_at':r[5].isoformat()} for r in cur.fetchall()]
    except psycopg.Error as exc: raise HTTPException(503,'Database unavailable or schema not installed') from exc
