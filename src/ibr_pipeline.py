"""
Chapter 14 - Image-Based Rendering
Adapted to process multiple real garment photo captures dynamically.

Techniques used, straight from the chapter, adapted to real images:
  1. Light Field Visualization  -> grid mosaic of the real viewpoints
  2. Depth Image-Based Rendering -> synthesize an in-between viewpoint
     from one real photo + an estimated depth map
  3. View Interpolation          -> morph between two real adjacent
     photos to manufacture extra in-between rotation frames
"""

import cv2
import numpy as np
import os
import glob

# ---------------------------------------------------------------------
# CORE PIPELINE FUNCTIONS
# ---------------------------------------------------------------------

def load_frames(garment_dir):
    """
    Loads real photos dynamically from the directional subfolders 
    in the correct 360-degree rotation order.
    """
    rotation_order = ["Front", "Right", "Back", "Left"]
    frames = []
    
    for angle in rotation_order:
        angle_dir = os.path.join(garment_dir, angle)
        if not os.path.exists(angle_dir):
            continue
            
        # Load images sorted by their numerical filename
        files = sorted(
            glob.glob(os.path.join(angle_dir, "*.jpg")),
            key=lambda p: int(os.path.splitext(os.path.basename(p))[0])
            if os.path.splitext(os.path.basename(p))[0].isdigit() else 0
        )
        
        for f in files:
            img = cv2.imread(f)
            if img is not None:
                frames.append(img)
            else:
                print(f"Warning: Could not read {f}")
                
    return frames


def create_light_field_grid(frames, cols=6, thumb_size=(220, 293)):
    """
    Lays out the real camera positions on a grid exactly like the
    book's `full_field = np.vstack(light_field)` step.
    """
    rows = int(np.ceil(len(frames) / cols))
    thumbs = [cv2.resize(f, thumb_size) for f in frames]

    blank = np.zeros((thumb_size[1], thumb_size[0], 3), dtype=np.uint8)
    while len(thumbs) < rows * cols:
        thumbs.append(blank)

    grid_rows = []
    for r in range(rows):
        row_imgs = thumbs[r * cols:(r + 1) * cols]
        grid_rows.append(np.hstack(row_imgs))
    full_field = np.vstack(grid_rows)
    return full_field


def render_with_depth(color_img, depth_img, shift_amount, baseline):
    """
    Renders a new viewpoint from a color image and its depth map.
    Uses a simple 3D warping approximation. (identical to the book code)
    """
    h, w = color_img.shape[:2]
    if depth_img.max() > 1:
        depth_norm = depth_img.astype(np.float32) / 255.0
    else:
        depth_norm = depth_img.astype(np.float32)

    y, x = np.mgrid[0:h, 0:w]
    x = x - w / 2
    y = y - h / 2

    focal_length = 500
    depth_epsilon = 0.1
    disparity = baseline * focal_length / (depth_norm * 100 + depth_epsilon)

    map_x = (x + disparity * shift_amount + w / 2).astype(np.float32)
    map_y = (y + h / 2).astype(np.float32)

    new_view = cv2.remap(color_img, map_x, map_y, cv2.INTER_LINEAR)
    return new_view


def estimate_pseudo_depth(color_img):
    """
    Estimates a plausible depth map using a saturation + brightness heuristic 
    and inverting it (close = dark value in the depth map, matching the book).
    """
    hsv = cv2.cvtColor(color_img, cv2.COLOR_BGR2HSV).astype(np.float32)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    foreground_score = (0.6 * sat + 0.4 * val)
    foreground_score = cv2.GaussianBlur(foreground_score, (25, 25), 0)
    norm = cv2.normalize(foreground_score, None, 0, 255, cv2.NORM_MINMAX)
    depth_img = (255 - norm).astype(np.uint8)  # close object -> low value
    return depth_img


def view_interpolation(img1, img2, alpha):
    """
    Linearly interpolates between two images.
    alpha: 0.0 returns img1, 1.0 returns img2. (identical to the book code)
    """
    if img1.shape[:2] != img2.shape[:2]:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
    img1_f = img1.astype(np.float32)
    img2_f = img2.astype(np.float32)
    interpolated = (1 - alpha) * img1_f + alpha * img2_f
    interpolated = np.clip(interpolated, 0, 255).astype(np.uint8)
    return interpolated


def build_interpolated_rotation(frames, steps_between=5):
    """
    Uses view_interpolation() to insert `steps_between` synthetic
    in-between frames between every pair of real adjacent photos.
    """
    h, w = frames[0].shape[:2]
    resized = [cv2.resize(f, (w, h)) for f in frames]

    sequence = []
    n = len(resized)
    for i in range(n):
        img1 = resized[i]
        img2 = resized[(i + 1) % n]
        sequence.append(img1)
        for s in range(1, steps_between + 1):
            alpha = s / (steps_between + 1)
            mid = view_interpolation(img1, img2, alpha)
            sequence.append(mid)
    return sequence


# ---------------------------------------------------------------------
# MAIN BATCH PROCESSING EXECUTION
# ---------------------------------------------------------------------
if __name__ == "__main__":
    SRC_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")
    OUT_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "ibr_out")

    if not os.path.exists(SRC_BASE):
        raise FileNotFoundError(f"Source directory not found: {SRC_BASE}")

    # Identify garment subdirectories (e.g., 'Blue Dress')
    garments = [d for d in os.listdir(SRC_BASE) if os.path.isdir(os.path.join(SRC_BASE, d))]

    if not garments:
        print("No garment directories found in images/. Exiting.")
        exit(0)

    for garment in garments:
        print(f"\n{'='*40}")
        print(f"PROCESSING GARMENT: {garment}")
        print(f"{'='*40}")
        
        garment_dir = os.path.join(SRC_BASE, garment)
        garment_out_dir = os.path.join(OUT_BASE, garment)
        os.makedirs(garment_out_dir, exist_ok=True)

        frames = load_frames(garment_dir)
        
        if not frames:
            print(f"No frames found for {garment}. Skipping...")
            continue
            
        print(f"Loaded {len(frames)} total raw frames.")

        # --- 1. Light field grid ---
        lf_grid = create_light_field_grid(frames)
        grid_path = os.path.join(garment_out_dir, "light_field_grid.jpg")
        cv2.imwrite(grid_path, lf_grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"Saved light_field_grid.jpg {lf_grid.shape}")

        # --- 2. Depth-based rendering on one real photo ---
        base = frames[0]
        depth = estimate_pseudo_depth(base)
        cv2.imwrite(os.path.join(garment_out_dir, "depth_map.jpg"), depth)

        synth_left = render_with_depth(base, depth, shift_amount=-0.6, baseline=2.0)
        synth_right = render_with_depth(base, depth, shift_amount=0.6, baseline=2.0)
        cv2.imwrite(os.path.join(garment_out_dir, "depth_rendered_left.jpg"), synth_left,
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(os.path.join(garment_out_dir, "depth_rendered_right.jpg"), synth_right,
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        print("Saved depth_map.jpg + depth_rendered_left/right.jpg")

        # --- 3. View interpolation strip ---
        # Safety check: if dataset is small, use frames 0 and 1. Otherwise use 4 and 5.
        idx_a = 4 if len(frames) > 5 else 0
        idx_b = 5 if len(frames) > 5 else 1
        
        img_a, img_b = frames[idx_a], frames[idx_b]
        img_b_resized = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        strip_imgs = [view_interpolation(img_a, img_b_resized, a)
                      for a in [0.0, 0.25, 0.5, 0.75, 1.0]]
        strip_thumbs = [cv2.resize(im, (160, 213)) for im in strip_imgs]
        strip = np.hstack(strip_thumbs)
        
        cv2.imwrite(os.path.join(garment_out_dir, "view_interpolation_strip.jpg"), strip,
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"Saved view_interpolation_strip.jpg (between frame {idx_a} and {idx_b})")

        # --- Build the full smoothed rotation sequence for the 360 viewer ---
        smooth_sequence = build_interpolated_rotation(frames, steps_between=2)
        seq_dir = os.path.join(garment_out_dir, "smooth_sequence")
        os.makedirs(seq_dir, exist_ok=True)
        
        for i, im in enumerate(smooth_sequence):
            cv2.imwrite(os.path.join(seq_dir, f"{i:03d}.jpg"), im,
                        [cv2.IMWRITE_JPEG_QUALITY, 78])
        print(f"Saved {len(smooth_sequence)} smoothed rotation frames to {seq_dir}")