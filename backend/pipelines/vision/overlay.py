"""
pipelines/vision/overlay.py
=============================
Draws debug visualisations on video frames.

Rendered elements per face:
  - Green/yellow/red bounding box (colour based on A_i(t) score)
  - Head pose axis arrows (Yaw/Pitch/Roll direction)
  - EAR value + drowsiness badge
  - Score breakdown bar (H_i | G_i | P_i | A_i)
  - Roll number label if assigned

Usage: Import draw_frame_overlay and call in the vision pipeline.
"""

import numpy as np
import cv2
from typing import List, Optional


def _score_color(score: float) -> tuple:
    """
    Returns BGR color based on score:
      1.0  → green  (attentive)
      0.5  → yellow (uncertain)
      0.0  → red    (distracted/drowsy)
    """
    if score >= 0.75:
        return (0, 220, 0)        # bright green
    elif score >= 0.50:
        return (0, 200, 220)      # yellow-ish
    else:
        return (0, 60, 220)       # red


def draw_face_box(
    frame: np.ndarray,
    bbox: tuple,
    attention_score: float,
    roll_no: Optional[int] = None,
    label: str = "",
) -> None:
    """Draw bounding box and name label on the frame."""
    x, y, w, h = bbox
    color = _score_color(attention_score)
    thickness = 2
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)

    # Student label
    display = f"Roll {roll_no}" if roll_no else label or "Unknown"
    cv2.rectangle(frame, (x, y - 22), (x + w, y), color, -1)
    cv2.putText(frame, display, (x + 4, y - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_score_bar(
    frame: np.ndarray,
    x: int,
    y: int,
    h_i: float,
    g_i: float,
    p_i: float,
    a_i: float,
    is_drowsy: bool = False,
) -> None:
    """Draw a compact score breakdown bar under the face."""
    bar_w  = 120
    seg_w  = bar_w // 4
    bar_h  = 14
    labels = [("H", h_i), ("G", g_i), ("P", p_i), ("A", a_i)]

    for i, (label, score) in enumerate(labels):
        sx = x + i * seg_w
        filled_w = int(seg_w * score)
        bg_color   = (50, 50, 50)
        fill_color = _score_color(score)

        cv2.rectangle(frame, (sx, y), (sx + seg_w, y + bar_h), bg_color, -1)
        cv2.rectangle(frame, (sx, y), (sx + filled_w, y + bar_h), fill_color, -1)
        cv2.putText(frame, f"{label}:{score:.2f}", (sx + 1, y + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, (255, 255, 255), 1, cv2.LINE_AA)

    if is_drowsy:
        cv2.putText(frame, "DROWSY!", (x, y + bar_h + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 60, 255), 2, cv2.LINE_AA)


def draw_head_pose_axes(
    frame: np.ndarray,
    landmarks_px: np.ndarray,
    yaw: float,
    pitch: float,
    roll: float,
    nose_tip_idx: int = 1,
    axis_len: int = 60,
) -> None:
    """Draw 3D head pose axis arrows originating from nose tip."""
    nose_x, nose_y = int(landmarks_px[nose_tip_idx][0]), int(landmarks_px[nose_tip_idx][1])
    origin = (nose_x, nose_y)

    yaw_r, pitch_r, roll_r = np.radians(yaw), np.radians(pitch), np.radians(roll)

    # Forward (Z-axis) → blue arrow indicates facing direction
    end_x = int(nose_x + axis_len * np.sin(yaw_r))
    end_y = int(nose_y - axis_len * np.sin(pitch_r))
    cv2.arrowedLine(frame, origin, (end_x, end_y), (255, 100, 0), 2, tipLength=0.25)

    # Yaw indicator (green left-right)
    yaw_end = (int(nose_x + axis_len * np.cos(yaw_r)), nose_y)
    cv2.arrowedLine(frame, origin, yaw_end, (0, 200, 0), 1, tipLength=0.25)

    # Text: angle values
    cv2.putText(frame,
                f"Y:{yaw:.1f} P:{pitch:.1f} R:{roll:.1f}",
                (nose_x - 40, nose_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 0), 1, cv2.LINE_AA)


def draw_hud(
    frame: np.ndarray,
    class_attention_pct: float,
    active_faces: int,
    session_paused: bool = False,
) -> None:
    """
    Top-left HUD showing session-level stats.
    """
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (280, 68), (30, 30, 30), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    color = _score_color(class_attention_pct / 100.0)
    status = "PAUSED" if session_paused else "ACTIVE"
    status_color = (0, 60, 255) if session_paused else (0, 200, 80)

    cv2.putText(frame, f"ClassAttn: {class_attention_pct:.1f}%",
                (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
    cv2.putText(frame, f"Faces: {active_faces}   [{status}]",
                (8, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1, cv2.LINE_AA)
    cv2.putText(frame, "Press Q to quit | P to pause",
                (8, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1, cv2.LINE_AA)


def draw_frame_overlay(
    frame: np.ndarray,
    face_results: list,
    class_attention_pct: float = 0.0,
    session_paused: bool = False,
) -> np.ndarray:
    """
    Master overlay function. Draws all visual elements on a copy of the frame.

    Args:
        frame             : Original BGR frame
        face_results      : List of dicts with keys:
                            bbox, h_i, g_i, p_i, a_i, ear, is_drowsy,
                            yaw, pitch, roll, landmarks_px, roll_no
        class_attention_pct: Overall class attention % for HUD
        session_paused    : Whether session is paused (for HUD display)

    Returns:
        annotated : BGR frame with overlays drawn
    """
    annotated = frame.copy()

    for result in face_results:
        bbox       = result.get("bbox", (0, 0, 0, 0))
        h_i        = result.get("h_i", 0.5)
        g_i        = result.get("g_i", 0.5)
        p_i        = result.get("p_i", 0.5)
        a_i        = result.get("a_i", 0.5)
        ear        = result.get("ear", 0.0)
        is_drowsy  = result.get("is_drowsy", False)
        yaw        = result.get("yaw", 0.0)
        pitch      = result.get("pitch", 0.0)
        roll       = result.get("roll", 0.0)
        lm_px      = result.get("landmarks_px", None)
        roll_no    = result.get("roll_no", None)

        x, y, w, h = bbox
        draw_face_box(annotated, bbox, a_i, roll_no=roll_no)
        draw_score_bar(annotated, x, y + h + 2, h_i, g_i, p_i, a_i, is_drowsy)

        if lm_px is not None:
            draw_head_pose_axes(annotated, lm_px, yaw, pitch, roll)

    draw_hud(annotated, class_attention_pct, len(face_results), session_paused)
    return annotated
