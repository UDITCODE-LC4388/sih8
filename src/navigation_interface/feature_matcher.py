"""
TRN Feature Matcher (Module 6 Component)

Performs scale-, rotation-, and translation-invariant visual feature matching
between real-time descent camera optical frames and the pre-stored 1m SR reference map.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import cv2
import numpy as np


class TRNFeatureMatcher:
    """ORB/AKAZE Feature Matching Engine for visual Terrain Relative Navigation."""

    def __init__(self, max_features: int = 1000):
        self.orb = cv2.ORB_create(nfeatures=max_features)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

    def match_descent_frame(
        self,
        descent_frame: np.ndarray,
        reference_ortho: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], int, float]:
        """
        Matches a descent camera frame against the SR reference orthoimage.
        
        Returns:
            Tuple of:
              - Homography matrix (3x3 float array or None if match failed)
              - Inlier match count
              - Match confidence score [0, 1]
        """
        # Ensure uint8
        img_desc = (descent_frame if descent_frame.dtype == np.uint8 else (descent_frame * 255).astype(np.uint8))
        img_ref = (reference_ortho if reference_ortho.dtype == np.uint8 else (reference_ortho * 255).astype(np.uint8))

        kp1, des1 = self.orb.detectAndCompute(img_desc, None)
        kp2, des2 = self.orb.detectAndCompute(img_ref, None)

        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return None, 0, 0.0

        matches = self.matcher.match(des1, des2)
        if len(matches) < 4:
            return None, len(matches), 0.0

        # Sort matches by distance
        matches = sorted(matches, key=lambda x: x.distance)

        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        homography, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        inlier_count = int(np.sum(mask)) if mask is not None else 0
        confidence = float(inlier_count / max(len(matches), 1))

        return homography, inlier_count, confidence
