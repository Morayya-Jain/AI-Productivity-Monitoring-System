"""Presence and phone usage detection using MediaPipe."""

import cv2
import mediapipe as mp
import numpy as np
import logging
from typing import Dict, Optional, Tuple, List
import math
import config

logger = logging.getLogger(__name__)


class PresenceDetector:
    """
    Detects student presence and phone usage using MediaPipe.
    
    Uses face detection for presence and pose/face mesh for
    head angle estimation to detect phone usage.
    """
    
    def __init__(self):
        """Initialize MediaPipe solutions."""
        # Face detection for presence
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0,  # 0 for short range (< 2m)
            min_detection_confidence=config.FACE_DETECTION_CONFIDENCE
        )
        
        # Face mesh for head pose estimation and eye tracking
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Hands detection for phone-holding gesture
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # State tracking for debouncing
        self.last_state = None
        self.state_frame_count = 0
        self.phone_frame_count = 0
    
    def __del__(self):
        """Clean up MediaPipe resources."""
        self.face_detection.close()
        self.face_mesh.close()
    
    def detect_presence(self, frame: np.ndarray) -> bool:
        """
        Detect if a face is present in the frame.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            True if face detected, False otherwise
        """
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process with face detection
        results = self.face_detection.process(rgb_frame)
        
        # Check if any faces detected
        if results.detections:
            return True
        
        return False
    
    def detect_phone_usage(self, frame: np.ndarray) -> bool:
        """
        Detect potential phone usage by analyzing head pose.
        
        Looks for head tilted down (looking at lap or phone) for
        a sustained duration.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            True if phone usage suspected, False otherwise
        """
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process with face mesh
        results = self.face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            # No face detected, reset counter
            self.phone_frame_count = 0
            return False
        
        # Get first face landmarks
        face_landmarks = results.multi_face_landmarks[0]
        
        # Calculate head tilt angle
        angle = self._calculate_head_tilt(face_landmarks, frame.shape)
        
        # Check if head is tilted down beyond threshold
        if angle is not None and angle > config.PHONE_DETECTION_ANGLE_THRESHOLD:
            self.phone_frame_count += 1
        else:
            self.phone_frame_count = 0
        
        # Need sustained head tilt for detection
        # Assuming ~1 FPS, this is roughly in seconds
        threshold_frames = config.PHONE_DETECTION_DURATION_SECONDS * config.DETECTION_FPS
        
        return self.phone_frame_count >= threshold_frames
    
    def _calculate_head_tilt(
        self,
        face_landmarks,
        image_shape: Tuple[int, int, int]
    ) -> Optional[float]:
        """
        Calculate head tilt angle from face landmarks.
        
        Uses nose tip and nose bridge landmarks to estimate
        head pitch (up/down tilt).
        
        Args:
            face_landmarks: MediaPipe face landmarks
            image_shape: Shape of the image (height, width, channels)
            
        Returns:
            Tilt angle in degrees (positive = looking down), or None if calculation fails
        """
        try:
            h, w, _ = image_shape
            
            # Key landmarks for head pose
            # 1 = nose tip, 168 = nose bridge top
            nose_tip = face_landmarks.landmark[1]
            nose_bridge = face_landmarks.landmark[168]
            
            # Convert normalized coordinates to pixel coordinates
            nose_tip_y = nose_tip.y * h
            nose_bridge_y = nose_bridge.y * h
            
            # Calculate vertical difference
            # If nose tip is significantly below bridge, head is tilted down
            y_diff = nose_tip_y - nose_bridge_y
            
            # Use nose tip depth (z coordinate) as additional indicator
            # Negative z means further from camera (head tilted down)
            z_factor = -nose_tip.z * 100  # Scale factor for sensitivity
            
            # Combine vertical position and depth for angle estimate
            # This is a simplified heuristic - not true 3D angle
            angle = (y_diff / h * 100) + z_factor
            
            return angle
            
        except Exception as e:
            logger.warning(f"Error calculating head tilt: {e}")
            return None
    
    def get_detection_state(self, frame: np.ndarray) -> Dict[str, bool]:
        """
        Get complete detection state for a frame.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            Dictionary with 'present' and 'phone_suspected' booleans
        """
        present = self.detect_presence(frame)
        phone_suspected = False
        
        # Only check for phone usage if person is present
        if present:
            phone_suspected = self.detect_phone_usage(frame)
        
        return {
            "present": present,
            "phone_suspected": phone_suspected
        }
    
    def determine_event_type(self, detection_state: Dict[str, bool]) -> str:
        """
        Determine the event type from detection state.
        
        Priority:
        1. Phone suspected (if present)
        2. Away (if not present)
        3. Present (default when present)
        
        Args:
            detection_state: Dictionary from get_detection_state
            
        Returns:
            Event type string (present, away, phone_suspected)
        """
        if not detection_state["present"]:
            return config.EVENT_AWAY
        elif detection_state["phone_suspected"]:
            return config.EVENT_PHONE_SUSPECTED
        else:
            return config.EVENT_PRESENT


def visualize_detection(
    frame: np.ndarray,
    detection_state: Dict[str, bool]
) -> np.ndarray:
    """
    Draw detection state on frame for debugging/visualization.
    
    Args:
        frame: Input frame
        detection_state: Detection state dictionary
        
    Returns:
        Frame with visualization overlay
    """
    frame_copy = frame.copy()
    
    # Status text
    if not detection_state["present"]:
        status = "AWAY"
        color = (0, 0, 255)  # Red
    elif detection_state["phone_suspected"]:
        status = "PHONE DETECTED"
        color = (0, 165, 255)  # Orange
    else:
        status = "PRESENT"
        color = (0, 255, 0)  # Green
    
    # Draw status box
    cv2.rectangle(frame_copy, (10, 10), (300, 60), (0, 0, 0), -1)
    cv2.putText(
        frame_copy,
        status,
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        color,
        2
    )
    
    return frame_copy


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    sys.path.insert(0, "..")
    from camera.capture import CameraCapture
    
    logging.basicConfig(level=logging.INFO)
    
    print("Testing presence detection...")
    print("Press 'q' to quit")
    
    detector = PresenceDetector()
    
    with CameraCapture() as camera:
        for frame in camera.frame_iterator():
            # Get detection state
            state = detector.get_detection_state(frame)
            event_type = detector.determine_event_type(state)
            
            # Visualize
            vis_frame = visualize_detection(frame, state)
            
            # Show frame
            cv2.imshow("Detection Test", vis_frame)
            
            # Print state
            print(f"State: {event_type} - Present: {state['present']}, Phone: {state['phone_suspected']}")
            
            # Exit on 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    cv2.destroyAllWindows()

