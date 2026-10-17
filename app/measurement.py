import math
from typing import Dict, List
import numpy as np
import cv2

FIELDS = {'tshirt':['chest_width','shirt_length','sleeve_length','shoulder_width'], 'jeans':['waist_width','hip_width','inseam','outseam','leg_opening']}

def distance(a,b):
    return math.hypot(float(a[0])-float(b[0]),float(a[1])-float(b[1]))

def calculate(reference_points, reference_cm, segments):
    if not (0.5 <= reference_cm <= 100): raise ValueError('Reference length must be between 0.5 and 100 cm')
    px=distance(*reference_points)
    if px < 15: raise ValueError('Reference points too close (minimum 15 pixels)')
    cm_per_px=reference_cm/px
    return {'calibration_pixels':round(px,3),'cm_per_pixel':cm_per_px,'measurements_cm':{k:round(distance(*v)*cm_per_px,2) for k,v in segments.items()}}

def segment_garment(image_bytes):
    arr=np.frombuffer(image_bytes,np.uint8)
    im=cv2.imdecode(arr,cv2.IMREAD_COLOR)
    if im is None: raise ValueError('Unsupported image')
    h,w=im.shape[:2]
    if w*h > 30_000_000: raise ValueError('Image exceeds 30 megapixels')
    scale=min(1.,1400/max(w,h))
    small=cv2.resize(im,None,fx=scale,fy=scale) if scale < 1 else im
    sh,sw=small.shape[:2]
    # Estimate plain background from perimeter, segment by LAB color distance.
    lab=cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32)
    border=np.concatenate([lab[:max(2,sh//30)].reshape(-1,3),lab[-max(2,sh//30):].reshape(-1,3),lab[:,:max(2,sw//30)].reshape(-1,3),lab[:,-max(2,sw//30):].reshape(-1,3)])
    bg=np.median(border,axis=0)
    dist=np.linalg.norm(lab-bg,axis=2)
    # Automatic mask is only a suggestion: no silent acceptance as ground truth.
    mask=np.uint8(dist>max(18.,float(np.percentile(dist,65))*.5))*255
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7))
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,kernel)
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel,iterations=2)
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    contours=[c for c in contours if cv2.contourArea(c)>sh*sw*.025]
    if not contours: return {'contour':[],'confidence':'low','note':'No clear garment silhouette; use manual endpoints'}
    c=max(contours,key=cv2.contourArea)
    epsilon=.003*cv2.arcLength(c,True)
    poly=cv2.approxPolyDP(c,epsilon,True).reshape(-1,2)
    poly=(poly/scale).round().astype(int).tolist()
    area=cv2.contourArea(c)/(sh*sw)
    touches=np.any(c[:,0,0]<=2) or np.any(c[:,0,0]>=sw-3) or np.any(c[:,0,1]<=2) or np.any(c[:,0,1]>=sh-3)
    confidence='low' if touches or area<.07 or area>.9 else 'medium'
    return {'contour':poly,'confidence':confidence,'note':'Boundary suggestion only; verify and manually select measurement endpoints. Avoid including ruler in silhouette.'}

def mae(pred,truth):
    keys=sorted(set(pred)&set(truth))
    if not keys: raise ValueError('No matching measurement keys')
    errors={k:round(abs(float(pred[k])-float(truth[k])),2) for k in keys}
    return {'absolute_errors_cm':errors,'mae_cm':round(sum(errors.values())/len(errors),3),'n':len(keys),'target_met':sum(errors.values())/len(errors)<=1}
