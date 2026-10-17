# Garment Vision — calibrated clothing measurements

A complete **manually verified measurement workflow** for T-shirts and jeans, with optional *experimental* OpenCV garment silhouette suggestions, mobile capture/gallery, pixel-to-cm calibration, FastAPI and PostgreSQL, and MAE reporting. **This is not a validated sub-1-cm automatic measurement system.** The 1 cm MAE is a test target, not a promised result.

## Windows quick start

1. Extract ZIP and open its `garment-vision-reliable` folder in VS Code.
2. Create environment: `py -3.11 -m venv .venv` (Python 3.11 or 3.12 recommended). Activate: `.venv\Scripts\Activate.ps1`.
3. `python -m pip install -r requirements.txt` then `python -m pip install pytest` (for tests).
4. In pgAdmin create a database named `clothing_measurements` if needed; open Query Tool on that database and execute `schema.sql`. **Existing `garments` table is not touched.**
5. Copy `.env.example` to `.env` and replace password, database name as appropriate. Never commit `.env`.
6. Start: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
7. On PC: `http://127.0.0.1:8000`. For phone on same Wi-Fi use `http://YOUR_PC_LOCAL_IP:8000` for gallery upload. Mobile camera capture may require HTTPS or supported browser/device. Avoid exposing server publicly without authentication.
8. Run unit tests: `python -m pytest -q`.

## How to measure

- Place flat garment on a contrasting uniform background. Ruler must be at same height/plane as garment. Use overhead photo, minimal perspective distortion, high resolution and even lighting.
- Choose T-shirt or jeans. Upload or capture. Optionally click **Suggest boundary**. The outline is a *hint only*, not measurement points.
- Enter known ruler segment length, then click its two endpoints on the photo. Click two endpoints for every named garment measurement in order. Undo and reset are available. Dots and lines render directly over the original image using its intrinsic coordinates, with no CSS `max-height` distortion.
- For jeans, widths mean *flat* garment widths, not circumference. Use the same hip-height location each time. Inseam should follow seam; the current straight-line measurement is a chord and can under-measure a curved seam. To improve this, take a sufficiently flat garment image or add polyline measurement as a future extension.
- Optionally enter independent manual ground-truth values for every measurement. The app computes absolute errors and mean absolute error (MAE). A result `target_met=true` means only that this **one record** met <=1 cm average error; it is not a global claim.
- Save. Each submission creates a **new** UUID record and never overwrites previous measurements. Image pixels are processed in-memory for contour suggestion; **image files are not stored** in the database or server.

## Validation protocol for your 4 garments

1. Measure 2 T-shirts and 2 jeans manually using a flexible tape and the exact same endpoint definitions; repeat each manual measurement three times and use the median. Keep all widths as flat widths.
2. For each garment, capture an overhead image with ruler in the garment plane. Record image resolution, reference length, ruler location and lighting.
3. Calibrate on 15 cm of ruler; measure a *different* known 10 cm segment in the image before measuring clothing. If >1 cm off, recapture/recalibrate.
4. Record each garment's predictions and manual values. The application displays MAE per garment. **Overall MAE** is sum of absolute errors over all 18 garment dimensions / 18. Compute overall result from saved records (sample query below). Also inspect max error and errors by dimension.
5. Re-run with different photo angles and phones to test generalization. Four garments are too few to establish accuracy in general.

```sql
SELECT ROUND(AVG(ABS((m.value)::numeric - (g.manual_truth_cm ->> m.key)::numeric)),3) AS overall_mae_cm,
       COUNT(*) AS compared_dimensions
FROM garment_measurements_v2 g,
LATERAL jsonb_each_text(g.measurements_cm) AS m(key,value)
WHERE g.manual_truth_cm IS NOT NULL
  AND g.manual_truth_cm ? m.key;
```

Note: query includes **all** validated records. If you retest the same garment, filter to your final four record UUIDs to avoid double counting.

## Engineering limitations and possible next upgrades

- Contour suggestion is simple LAB-background separation. It is not an ML-trained garment landmark model and may include shadows/rulers or fail on complex backgrounds. The app does not infer measurement endpoints from contour because that would produce unreliable results without garment-specific landmark training.
- A single ruler only corrects scale for the ruler's plane; perspective, camera tilt and non-flat cloth cause systematic errors. For higher reliability, add ArUco/ChArUco planar homography with four corner markers, camera undistortion and geometric quality gates.
- Tap precision on phones may be limited; use high-resolution images and verify point placement. No automated <1 cm accuracy guarantee.
- Current lengths are straight lines, not polyline paths. Inseam/outseam curves may need segmented path support.
- App has no authentication; use only on trusted local networks until secured. `.env` holds DB credentials. Do not use the development server publicly.

## API

`GET /api/health`, `POST /api/contour` (multipart image), `POST /api/measurements` (JSON), `GET /api/records`.

