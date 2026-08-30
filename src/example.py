'''Chapter 14 Image-Based Rendering 

The codes demonstrate core rendering techniques like creating a synthetic viewpoint through interpolation and visualizing a scene from different perspectives. 

 

1. Light Field Visualization 

This Python code creates a simple light field by simulating the view of an object from different camera positions and allows you to visualize these different views. This builds a foundation for understanding how light field data can be captured and then re-rendered from new perspectives. '''

 

import cv2 

import numpy as np 

 

def create_light_field(): 

    """ 

    Simulates a 4D light field by rendering a 3D object from various viewpoints. 

    In a real scenario, a light field is captured by a camera array or a single 

    camera moving along a grid. 

    """ 

    # Define a simple 3D scene: a blue square acting as an object 

    scene = np.zeros((200, 200, 3), dtype=np.uint8) 

    # Draw a blue object (representing a 3D object in the scene) 

    cv2.rectangle(scene, (50, 50), (150, 150), (255, 0, 0), -1) 

 

    light_field = [] 

    # Simulate viewpoints along a small grid (u, v) 

    for v in range(5):  # v (vertical) position 

        row = [] 

        for u in range(5):  # u (horizontal) position 

            # Create a copy of the scene 

            view = scene.copy() 

            # Simulate perspective change by shifting the object 

            # This is a highly simplified approximation 

            shift_x = (u - 2) * 5 

            shift_y = (v - 2) * 5 

            M = np.float32([[1, 0, shift_x], [0, 1, shift_y]]) 

            view = cv2.warpAffine(view, M, (view.shape[1], view.shape[0])) 

            row.append(view) 

        # Vertically stack the row to create the light field display 

        light_field.append(np.hstack(row)) 

 

    # Vertically stack all rows to form the final light field image 

    full_field = np.vstack(light_field) 

    return full_field 

 

# Display the light field 

light_field_img = create_light_field() 

cv2.imshow('Light Field Visualization (Viewpoints)', light_field_img) 

print("Light Field Simulation: Each sub-image represents a different viewpoint.") 

print("Press any key to close the window.") 

cv2.waitKey(0) 

cv2.destroyAllWindows() 

 

 
''''2. Depth Map and Virtual Viewpoint 

This Python code uses a depth map to create a new, synthetic viewpoint of a scene via a simple rendering technique known as depth image-based rendering. It approximates the 3D geometry of the scene by displacing pixels based on their depth to synthesize a new perspective. '''


 

import cv2 

import numpy as np 

 

def render_with_depth(color_img, depth_img, shift_amount, baseline): 

    """ 

    Renders a new viewpoint from a color image and its depth map. 

    Uses a simple 3D warping approximation. 

    """ 

    h, w = color_img.shape[:2] 

    # Normalize the depth image to a range between 0 and 1 

    if depth_img.max() > 1: 

        depth_norm = depth_img.astype(np.float32) / 255.0 

    else: 

        depth_norm = depth_img.astype(np.float32) 

 

    # Create a 3D grid of pixel coordinates 

    y, x = np.mgrid[0:h, 0:w] 

    # Convert pixel coordinates to be centered at the image center 

    x = x - w / 2 

    y = y - h / 2 

 

    # Focal length and baseline to control disparity 

    # Disparity is inversely proportional to depth 

    focal_length = 500 

    # To avoid division by zero in a real scenario, add a small epsilon 

    # Here we use a trick: disparity = 1 / (depth + 0.1) 

    depth_epsilon = 0.1 

    # Calculate disparity. For objects with high depth (white), disparity is small. 

    disparity = baseline * focal_length / (depth_norm * 100 + depth_epsilon) 

 

    # Displace pixels based on depth to synthesize a new viewpoint 

    # For a shift in viewpoint, pixels with small depth (close) move more 

    map_x = (x + disparity * shift_amount + w / 2).astype(np.float32) 

    map_y = (y + h / 2).astype(np.float32) 

 

    # Remap the color image using the calculated maps 

    # Warp mode: cv2.INTER_LINEAR for smooth interpolation 

    new_view = cv2.remap(color_img, map_x, map_y, cv2.INTER_LINEAR) 

    return new_view 

 

# Create synthetic color and depth images 

# A 300x300 black background 

color_img = np.zeros((300, 300, 3), dtype=np.uint8) 

# A 300x300 depth map (0-255, where 0 is close, 255 is far) 

depth_img = np.zeros((300, 300), dtype=np.uint8) 

 

# Draw an object (a red square) and define its depth 

cv2.rectangle(color_img, (100, 100), (200, 200), (0, 0, 255), -1) 

# Assign a close depth (dark) to the red square 

cv2.rectangle(depth_img, (100, 100), (200, 200), 50, -1) 

# Assign a far depth (light) to the background 

depth_img = cv2.bitwise_not(depth_img) # Inverts depth so black is close, white is far 

 

# Simulate a baseline (distance between cameras) for a stereo system 

baseline = 2.0 

 

# Render a new viewpoint by shifting right (positive shift amount) 

new_view = render_with_depth(color_img, depth_img, shift_amount=0.5, baseline=baseline) 

 

cv2.imshow('Original View', color_img) 

cv2.imshow('Depth Map', depth_img) 

cv2.imshow('Rendered New Viewpoint', new_view) 

print("Rendering a new viewpoint using depth information.") 

print("The red square (close object) moves more than the background.") 

print("Press any key to close the windows.") 

cv2.waitKey(0) 

cv2.destroyAllWindows() 

 

 


'''""3. View Interpolation 

This code demonstrates a fundamental rendering technique: creating a smooth transition or a "morph" between two images. View interpolation is a key idea in image-based rendering, as it allows for the generation of a virtual camera path between two captured viewpoints.  '''
 

import cv2 

import numpy as np 

 

def view_interpolation(img1, img2, alpha): 

    """ 

    Linearly interpolates between two images. 

    alpha: 0.0 returns img1, 1.0 returns img2. 

    """ 

    # Ensure both images have the same dimensions and type 

    if img1.shape != img2.shape: 

        print("Images must have the same dimensions.") 

        return None 

 

    # Convert images to float for precise calculations 

    img1_f = img1.astype(np.float32) 

    img2_f = img2.astype(np.float32) 

 

    # Perform linear interpolation (alpha blending) 

    interpolated = (1 - alpha) * img1_f + alpha * img2_f 

 

    # Convert back to uint8 (0-255) 

    interpolated = np.clip(interpolated, 0, 255).astype(np.uint8) 

    return interpolated 

 

# Load two images of the same scene from different viewpoints. 

# Using the provided sample images or create your own. 

# For example: 

# img1 = cv2.imread('view1.jpg') 

# img2 = cv2.imread('view2.jpg') 

 

# Create synthetic images to demonstrate the concept 

img1 = np.zeros((300, 300, 3), dtype=np.uint8) 

cv2.rectangle(img1, (50, 50), (150, 150), (255, 0, 0), -1) # Blue square 

 

img2 = np.zeros((300, 300, 3), dtype=np.uint8) 

cv2.rectangle(img2, (100, 100), (200, 200), (0, 0, 255), -1) # Red square 

 

# Interpolate between the two views (alpha=0.5 for the middle view) 

alpha = 0.5  # 0.5 gives a perfect blend. Try other values like 0.25 or 0.75. 

middle_view = view_interpolation(img1, img2, alpha) 

 

cv2.imshow('View 1', img1) 

cv2.imshow('View 2', img2) 

if middle_view is not None: 

    cv2.imshow('Interpolated View', middle_view) 

print("View Interpolation: A simple morph between two images.") 

print("Press any key to close the windows.") 

cv2.waitKey(0) 

cv2.destroyAllWindows() 

 