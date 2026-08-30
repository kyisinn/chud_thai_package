"""
Chud Thai (Thai Chakraphat) -- 3D Reconstruction Pipeline
=========================================================
Museum Images -> Selection -> Pre-processing -> Alignment ->
Feature Detection & Matching -> Motion Estimation ->
Camera/Viewpoint Estimation -> 3D Reconstruction ->
Texture Mapping -> 3D Rendering -> Visual Evaluation ->
Final Digital Chud Thai Model

Honest scope note (read this before trusting the output):
  These are 18 handheld phone photos of a museum piece behind glass,
  taken from roughly-but-not-evenly spaced angles, no calibration
  target, no EXIF focal length, and with glare/reflections in several
  frames. That is a genuinely hard case for classical Structure-from-
  Motion (SfM). This script implements every stage for real using
  OpenCV + Open3D and will produce a real (if sparse and noisy) 3D
  point cloud -- it is NOT a substitute for a proper photogrammetry
  tool (COLMAP / RealityCapture / Metashape) run on a clean, evenly
  spaced turntable capture, which is what you'd want for a museum-
  grade "Final Digital Chud Thai Model".
"""

import cv2
import numpy as np
import open3d as o3d
import os
import json

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "sfm_out")
os.makedirs(OUT_DIR, exist_ok=True)

NUM_IMAGES = 18


# ---------------------------------------------------------------------
# 1. IMAGE COLLECTION & SELECTION
# ---------------------------------------------------------------------
def collect_and_select_images():
    kept = []
    rejected = []
    for i in range(1, NUM_IMAGES + 1):
        path = os.path.join(SRC_DIR, f"{i}.jpg")
        img = cv2.imread(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness > 15:
            kept.append((i, img))
        else:
            rejected.append((i, sharpness))
    print(f"[1] Selection: kept {len(kept)}/{NUM_IMAGES} images "
          f"(rejected: {rejected})")
    return kept


# ---------------------------------------------------------------------
# 2. IMAGE PRE-PROCESSING
# ---------------------------------------------------------------------
def preprocess(img, target_width=900):
    h, w = img.shape[:2]
    scale = target_width / w
    img = cv2.resize(img, (target_width, int(h * scale)))

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    img = cv2.fastNlMeansDenoisingColored(img, None, 3, 3, 7, 15)
    return img


# ---------------------------------------------------------------------
# 3. IMAGE ALIGNMENT (coarse overlap check, real alignment = pose est.)
# ---------------------------------------------------------------------
def coarse_align_preview(images, ref_idx=0):
    orb = cv2.ORB_create(1500)
    ref_gray = cv2.cvtColor(images[ref_idx], cv2.COLOR_BGR2GRAY)
    kp_ref, des_ref = orb.detectAndCompute(ref_gray, None)

    overlaps = []
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    for img in images:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kp, des = orb.detectAndCompute(gray, None)
        if des is None or des_ref is None:
            overlaps.append(0)
            continue
        matches = bf.match(des_ref, des)
        overlaps.append(len(matches))
    print(f"[3] Alignment/overlap check vs frame {ref_idx}: "
          f"match counts = {overlaps}")
    return overlaps


# ---------------------------------------------------------------------
# 4. FEATURE DETECTION & MATCHING
# ---------------------------------------------------------------------
def detect_and_match_features(images, ratio_thresh=0.75):
    sift = cv2.SIFT_create(nfeatures=4000)
    keypoints, descriptors = [], []
    for img in images:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kp, des = sift.detectAndCompute(gray, None)
        keypoints.append(kp)
        descriptors.append(des)

    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    pair_matches = {}
    for i in range(len(images) - 1):
        des1, des2 = descriptors[i], descriptors[i + 1]
        if des1 is None or des2 is None or len(des1) < 8 or len(des2) < 8:
            pair_matches[(i, i + 1)] = []
            continue
        raw = flann.knnMatch(des1.astype(np.float32),
                              des2.astype(np.float32), k=2)
        good = [m for m, n in raw if m.distance < ratio_thresh * n.distance]
        pair_matches[(i, i + 1)] = good
        print(f"[4] pair ({i},{i+1}): {len(good)} good matches / "
              f"{len(raw)} candidates")

    return keypoints, descriptors, pair_matches


# ---------------------------------------------------------------------
# 5. MOTION ESTIMATION
# ---------------------------------------------------------------------
def estimate_motion(keypoints, pair_matches, img_shape):
    motions = {}
    for (i, j), matches in pair_matches.items():
        if not matches:
            motions[(i, j)] = None
            continue
        pts1 = np.float32([keypoints[i][m.queryIdx].pt for m in matches])
        pts2 = np.float32([keypoints[j][m.trainIdx].pt for m in matches])
        disp = pts2 - pts1
        mean_disp = disp.mean(axis=0)
        mean_mag = np.linalg.norm(disp, axis=1).mean()
        motions[(i, j)] = {
            "mean_dx_dy": mean_disp.tolist(),
            "mean_magnitude_px": float(mean_mag),
        }
        print(f"[5] motion ({i},{j}): mean displacement = "
              f"{mean_disp.round(1).tolist()} px, "
              f"mean magnitude = {mean_mag:.1f} px")
    return motions


# ---------------------------------------------------------------------
# 6. CAMERA / VIEWPOINT ESTIMATION
# ---------------------------------------------------------------------
def estimate_camera_poses(keypoints, pair_matches, img_shape,
                           min_inlier_matches=15):
    h, w = img_shape[:2]
    f = max(w, h)
    K = np.array([[f, 0, w / 2],
                  [0, f, h / 2],
                  [0, 0, 1]], dtype=np.float64)

    global_pose = np.eye(4)
    poses = {0: global_pose.copy()}
    relative_poses = {}

    for i in range(len(keypoints) - 1):
        matches = pair_matches.get((i, i + 1), [])
        if len(matches) < min_inlier_matches:
            print(f"[6] pair ({i},{i+1}): too few matches "
                  f"({len(matches)}) -- pose skipped")
            relative_poses[(i, i + 1)] = None
            poses[i + 1] = poses[i].copy()
            continue

        pts1 = np.float32([keypoints[i][m.queryIdx].pt for m in matches])
        pts2 = np.float32([keypoints[i + 1][m.trainIdx].pt for m in matches])

        E, mask = cv2.findEssentialMat(pts1, pts2, K,
                                        method=cv2.RANSAC,
                                        prob=0.999, threshold=1.0)
        if E is None:
            relative_poses[(i, i + 1)] = None
            poses[i + 1] = poses[i].copy()
            continue

        _, R, t, mask_pose = cv2.recoverPose(E, pts1, pts2, K, mask=mask)
        inliers = int(mask_pose.sum())
        print(f"[6] pair ({i},{i+1}): {inliers}/{len(matches)} pose inliers")

        T_rel = np.eye(4)
        T_rel[:3, :3] = R
        T_rel[:3, 3] = t.flatten()
        relative_poses[(i, i + 1)] = T_rel

        global_pose = global_pose @ T_rel
        poses[i + 1] = global_pose.copy()

    return K, poses, relative_poses


# ---------------------------------------------------------------------
# 7. 3D COSTUME RECONSTRUCTION (sparse triangulation)
# ---------------------------------------------------------------------
def reconstruct_3d(images, keypoints, pair_matches, K, poses,
                    relative_poses, min_inlier_matches=15):
    all_points = []
    all_colors = []

    for i in range(len(images) - 1):
        T_rel = relative_poses.get((i, i + 1))
        matches = pair_matches.get((i, i + 1), [])
        if T_rel is None or len(matches) < min_inlier_matches:
            continue

        pts1 = np.float32([keypoints[i][m.queryIdx].pt for m in matches]).T
        pts2 = np.float32([keypoints[i + 1][m.trainIdx].pt for m in matches]).T

        P1 = K @ np.eye(3, 4)
        R, t = T_rel[:3, :3], T_rel[:3, 3:4]
        P2 = K @ np.hstack([R, t])

        pts4d = cv2.triangulatePoints(P1, P2, pts1, pts2)
        pts3d = (pts4d[:3] / pts4d[3]).T

        depths = pts3d[:, 2]
        valid = (depths > 0.05) & (depths < 50)
        pts3d = pts3d[valid]

        Pg = poses[i]
        pts3d_h = np.hstack([pts3d, np.ones((pts3d.shape[0], 1))])
        pts3d_global = (Pg @ pts3d_h.T).T[:, :3]

        valid_matches = [m for k, m in enumerate(matches) if valid[k]]
        colors = []
        for m in valid_matches:
            x, y = keypoints[i][m.queryIdx].pt
            x, y = int(round(x)), int(round(y))
            x = np.clip(x, 0, images[i].shape[1] - 1)
            y = np.clip(y, 0, images[i].shape[0] - 1)
            b, g, r = images[i][y, x]
            colors.append([r / 255.0, g / 255.0, b / 255.0])

        all_points.append(pts3d_global)
        all_colors.append(np.array(colors))
        print(f"[7] pair ({i},{i+1}): triangulated {len(pts3d_global)} "
              f"3D points")

    if not all_points:
        raise RuntimeError("No pairs produced a valid pose -- reconstruction failed.")

    points = np.vstack(all_points)
    colors = np.vstack(all_colors)
    print(f"[7] Total sparse point cloud: {len(points)} points")
    return points, colors


# ---------------------------------------------------------------------
# 8. TEXTURE MAPPING (surface reconstruction + vertex color)
# ---------------------------------------------------------------------
def texture_map(points, colors):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)

    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(
        radius=0.5, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(30)

    mesh = None
    try:
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=8)
        densities = np.asarray(densities)
        thresh = np.quantile(densities, 0.15)
        keep = densities > thresh
        mesh.remove_vertices_by_mask(~keep)
        print(f"[8] Poisson mesh: {len(mesh.vertices)} verts, "
              f"{len(mesh.triangles)} tris after low-density trim")
    except Exception as e:
        print(f"[8] Poisson reconstruction failed ({e}); "
              f"falling back to colored point cloud only")

    return pcd, mesh


# ---------------------------------------------------------------------
# 9. 3D RENDERING
# ---------------------------------------------------------------------
def render_3d(pcd, mesh, out_dir):
    o3d.io.write_point_cloud(os.path.join(out_dir, "sparse_cloud.ply"), pcd)
    if mesh is not None and len(mesh.vertices) > 0:
        o3d.io.write_triangle_mesh(os.path.join(out_dir, "mesh.ply"), mesh)

    render_paths = []
    try:
        vis = o3d.visualization.Visualizer()
        vis.create_window(visible=False, width=800, height=800)
        geom = mesh if (mesh is not None and len(mesh.vertices) > 0) else pcd
        vis.add_geometry(geom)
        ctr = vis.get_view_control()

        for angle_idx, yaw in enumerate([0, 90, 180, 270]):
            ctr.rotate(yaw * 3.0, 0)
            vis.poll_events()
            vis.update_renderer()
            out_path = os.path.join(out_dir, f"render_{angle_idx:02d}.png")
            vis.capture_screen_image(out_path, do_render=True)
            render_paths.append(out_path)
        vis.destroy_window()
        print(f"[9] Rendered {len(render_paths)} preview angles")
    except Exception as e:
        print(f"[9] Offscreen rendering unavailable on this machine ({e}). "
              f"sparse_cloud.ply / mesh.ply were still saved -- open them "
              f"in MeshLab, Blender, or CloudCompare to view/rotate in 3D.")
    return render_paths


# ---------------------------------------------------------------------
# 10. VISUAL EVALUATION
# ---------------------------------------------------------------------
def evaluate(keypoints, pair_matches, points, mesh, out_dir):
    report = {
        "num_images": len(keypoints),
        "keypoints_per_image": [len(k) for k in keypoints],
        "matches_per_pair": {f"{i}-{j}": len(m)
                              for (i, j), m in pair_matches.items()},
        "total_sparse_points": int(len(points)),
        "mesh_vertices": int(len(mesh.vertices)) if mesh is not None else 0,
        "mesh_triangles": int(len(mesh.triangles)) if mesh is not None else 0,
    }
    with open(os.path.join(out_dir, "evaluation_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("[10] Evaluation report:", json.dumps(report, indent=2))
    return report


# ---------------------------------------------------------------------
# PIPELINE ENTRY POINT
# ---------------------------------------------------------------------
if __name__ == "__main__":
    selected = collect_and_select_images()
    raw_images = [img for _, img in selected]
    images = [preprocess(img) for img in raw_images]
    coarse_align_preview(images)
    keypoints, descriptors, pair_matches = detect_and_match_features(images)
    motions = estimate_motion(keypoints, pair_matches, images[0].shape)
    K, poses, relative_poses = estimate_camera_poses(
        keypoints, pair_matches, images[0].shape)
    points, colors = reconstruct_3d(
        images, keypoints, pair_matches, K, poses, relative_poses)
    pcd, mesh = texture_map(points, colors)
    render_paths = render_3d(pcd, mesh, OUT_DIR)
    report = evaluate(keypoints, pair_matches, points, mesh, OUT_DIR)

    print("\nDone. Outputs in", OUT_DIR)
