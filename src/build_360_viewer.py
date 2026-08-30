"""
Builds the self-contained 360 rotate HTML viewer from whichever frame
sequence is available:
  - outputs/ibr_out/smooth_sequence/*.jpg  (54 view-interpolated frames,
    produced by ibr_pipeline.py)  -- preferred, smoother rotation
  - images/*.jpg                            (18 raw photos) -- fallback
"""

import base64
import glob
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SMOOTH_DIR = os.path.join(ROOT, "outputs", "ibr_out", "smooth_sequence")
RAW_DIR = os.path.join(ROOT, "images")
OUT_HTML = os.path.join(ROOT, "viewer", "thai_chakraphat_360.html")
TMP_DIR = os.path.join(ROOT, "outputs", "_viewer_tmp")

os.makedirs(os.path.join(ROOT, "viewer"), exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)


def collect_frames():
    smooth_files = sorted(glob.glob(os.path.join(SMOOTH_DIR, "*.jpg")))
    if smooth_files:
        print(f"Using {len(smooth_files)} view-interpolated frames from "
              f"ibr_pipeline.py output")
        return smooth_files
    raw_files = sorted(
        glob.glob(os.path.join(RAW_DIR, "*.jpg")),
        key=lambda p: int(os.path.splitext(os.path.basename(p))[0])
        if os.path.splitext(os.path.basename(p))[0].isdigit() else 0
    )
    print(f"No smoothed sequence found; falling back to "
          f"{len(raw_files)} raw photos. Run ibr_pipeline.py first for "
          f"a smoother result.")
    return raw_files


def resize_and_encode(files, max_width=480, quality=68):
    b64_list = []
    for f in files:
        im = Image.open(f).convert("RGB")
        w, h = im.size
        new_w = min(max_width, w)
        new_h = int(h * (new_w / w))
        im = im.resize((new_w, new_h), Image.LANCZOS)
        tmp_path = os.path.join(TMP_DIR, os.path.basename(f))
        im.save(tmp_path, "JPEG", quality=quality, optimize=True)
        with open(tmp_path, "rb") as fh:
            data = fh.read()
        b64_list.append(base64.b64encode(data).decode("ascii"))
    return b64_list


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Thai Chakraphat -- 360 Viewer</title>
<style>
  :root { --gold: #c9a24a; --bg: #0e0d0b; --panel: #17151198; }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: radial-gradient(ellipse at center, #1b1812 0%, #080706 100%);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    color: #eee7d6; overflow: hidden;
  }
  .wrap { height: 100%; display: flex; flex-direction: column;
    align-items: center; justify-content: center; padding: 16px; }
  h1 { font-size: 1.05rem; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--gold); margin: 0 0 4px 0;
    text-align: center; }
  .sub { font-size: 0.78rem; color: #a89f89; margin-bottom: 14px;
    text-align: center; }
  .stage { position: relative; width: min(78vw, 420px);
    height: min(72vh, 560px); border-radius: 14px; overflow: hidden;
    background: linear-gradient(180deg, #201c15 0%, #100e0b 100%);
    box-shadow: 0 0 0 1px #3a331fcc, 0 20px 60px -10px #000c,
      inset 0 0 40px #0008;
    cursor: grab; user-select: none; touch-action: none; }
  .stage:active { cursor: grabbing; }
  .stage img { position: absolute; top: 0; left: 0; width: 100%;
    height: 100%; object-fit: contain; pointer-events: none;
    -webkit-user-drag: none; opacity: 0; transition: opacity 0.03s linear; }
  .stage img.active { opacity: 1; }
  .hint { position: absolute; bottom: 10px; left: 50%;
    transform: translateX(-50%); font-size: 0.72rem; color: #d8cba7;
    background: var(--panel); padding: 5px 12px; border-radius: 20px;
    backdrop-filter: blur(4px); display: flex; align-items: center;
    gap: 6px; pointer-events: none; transition: opacity 0.4s ease; }
  .hint svg { width: 14px; height: 14px; }
  .hint.hide { opacity: 0; }
  .controls { display: flex; align-items: center; gap: 14px; margin-top: 16px; }
  button.ctrl { background: #1c1811; border: 1px solid #45391f;
    color: var(--gold); width: 38px; height: 38px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; transition: background 0.15s, transform 0.15s; }
  button.ctrl:hover { background: #2a2416; transform: scale(1.06); }
  button.ctrl svg { width: 16px; height: 16px; fill: var(--gold); }
  .slider-row { display: flex; align-items: center; gap: 10px;
    width: min(78vw, 420px); margin-top: 12px; }
  input[type=range] { flex: 1; -webkit-appearance: none; height: 3px;
    border-radius: 3px; background: #3a331f; outline: none; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none;
    width: 13px; height: 13px; border-radius: 50%; background: var(--gold);
    cursor: pointer; box-shadow: 0 0 6px #c9a24a99; }
  .frame-count { font-size: 0.7rem; color: #a89f89; min-width: 50px;
    text-align: right; font-variant-numeric: tabular-nums; }
  .auto-label { font-size: 0.68rem; color: #a89f89; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Thai Chakraphat</h1>
    <div class="sub">__SUBTITLE__</div>
    <div class="stage" id="stage">
      <div class="hint" id="hint">
        <svg viewBox="0 0 24 24"><path d="M9 3L5 6.99h3V14h2V6.99h3L9 3zm7 14.01V10h-2v7.01h-3L15 21l4-3.99h-3z"/></svg>
        drag to rotate
      </div>
    </div>
    <div class="controls">
      <button class="ctrl" id="prevBtn" title="Previous frame">
        <svg viewBox="0 0 24 24"><path d="M15.4 7.4L14 6l-6 6 6 6 1.4-1.4L10.8 12z"/></svg>
      </button>
      <button class="ctrl" id="playBtn" title="Auto-rotate">
        <svg id="playIcon" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
      </button>
      <button class="ctrl" id="nextBtn" title="Next frame">
        <svg viewBox="0 0 24 24"><path d="M8.6 7.4L10 6l6 6-6 6-1.4-1.4L13.2 12z"/></svg>
      </button>
    </div>
    <div class="slider-row">
      <span class="auto-label">1</span>
      <input type="range" id="slider" min="0" max="__MAXFRAME__" value="0" step="1">
      <span class="frame-count" id="frameCount">1 / __TOTAL__</span>
    </div>
  </div>
<script>
const FRAMES = [
__FRAMES_JS__
];
const stage = document.getElementById('stage');
const slider = document.getElementById('slider');
const frameCount = document.getElementById('frameCount');
const hint = document.getElementById('hint');
const playBtn = document.getElementById('playBtn');
const playIcon = document.getElementById('playIcon');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
let current = 0, isDragging = false, startX = 0, startFrame = 0, autoPlay = null;
const DRAG_SENSITIVITY = 6;
const imgEls = FRAMES.map((src, i) => {
  const img = document.createElement('img');
  img.src = src; img.draggable = false;
  if (i === 0) img.classList.add('active');
  stage.appendChild(img);
  return img;
});
function setFrame(idx) {
  idx = ((idx % FRAMES.length) + FRAMES.length) % FRAMES.length;
  if (idx === current) return;
  imgEls[current].classList.remove('active');
  imgEls[idx].classList.add('active');
  current = idx; slider.value = idx;
  frameCount.textContent = (idx + 1) + " / " + FRAMES.length;
}
function stopAuto() {
  if (autoPlay) { clearInterval(autoPlay); autoPlay = null;
    playIcon.innerHTML = '<path d="M8 5v14l11-7z"/>'; }
}
function toggleAuto() {
  if (autoPlay) { stopAuto(); } else {
    playIcon.innerHTML = '<rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/>';
    autoPlay = setInterval(() => setFrame(current + 1), 130);
  }
}
function pointerDown(e) {
  stopAuto(); isDragging = true;
  startX = (e.touches ? e.touches[0].clientX : e.clientX);
  startFrame = current; hint.classList.add('hide'); stage.style.cursor = 'grabbing';
}
function pointerMove(e) {
  if (!isDragging) return;
  const x = (e.touches ? e.touches[0].clientX : e.clientX);
  const dx = x - startX;
  const delta = Math.round(-dx / DRAG_SENSITIVITY);
  setFrame(startFrame + delta);
}
function pointerUp() { isDragging = false; stage.style.cursor = 'grab'; }
stage.addEventListener('mousedown', pointerDown);
window.addEventListener('mousemove', pointerMove);
window.addEventListener('mouseup', pointerUp);
stage.addEventListener('touchstart', pointerDown, {passive: true});
window.addEventListener('touchmove', pointerMove, {passive: true});
window.addEventListener('touchend', pointerUp);
slider.addEventListener('input', () => { stopAuto(); setFrame(parseInt(slider.value, 10)); });
prevBtn.addEventListener('click', () => { stopAuto(); setFrame(current - 1); });
nextBtn.addEventListener('click', () => { stopAuto(); setFrame(current + 1); });
playBtn.addEventListener('click', toggleAuto);
window.addEventListener('load', () => {
  setTimeout(() => { toggleAuto(); setTimeout(stopAuto, 2200); }, 500);
});
</script>
</body>
</html>
"""


def main():
    files = collect_frames()
    if not files:
        raise RuntimeError("No frames found in outputs/ibr_out/smooth_sequence "
                            "or images/. Nothing to build.")
    b64_list = resize_and_encode(files)
    frames_js = ",\n".join([f'"data:image/jpeg;base64,{b}"' for b in b64_list])

    subtitle = ("360&deg; interactive garment viewer &mdash; "
                 f"{len(files)} frames "
                 f"({'18 real photos + view-interpolated in-between frames' if len(files) > 18 else 'raw captured photos'})")

    html = HTML_TEMPLATE
    html = html.replace("__FRAMES_JS__", frames_js)
    html = html.replace("__MAXFRAME__", str(len(files) - 1))
    html = html.replace("__TOTAL__", str(len(files)))
    html = html.replace("__SUBTITLE__", subtitle)
    html = html.replace('1 / __TOTAL__', f'1 / {len(files)}')

    with open(OUT_HTML, "w") as f:
        f.write(html)

    print(f"Wrote {OUT_HTML} ({os.path.getsize(OUT_HTML)/1e6:.2f} MB, "
          f"{len(files)} frames)")


if __name__ == "__main__":
    main()
