import cv2
import argparse
import multiprocessing as mp
import mediapipe as mdp
import os
import os.path as osp
import sys
BUILD_DIR = osp.join(osp.dirname(osp.abspath(__file__)), "build/service/")
sys.path.insert(0, BUILD_DIR)
import grpc
from concurrent import futures

import control_pb2
import control_pb2_grpc

mdp_hands = mdp.solutions.hands
mdp_object_detection = mdp.solutions.object_detection
mdp_drawing_styles = mdp.solutions.drawing_styles
mdp_drawing = mdp.solutions.drawing_utils
mdp_pose = mdp.solutions.pose

fps = 10
width = 1920
height = 1080
# TASK = {"OD": False, "HPT": False, "PE": False}

class ControlServicer(control_pb2_grpc.ControlServicer):

    def __init__(self):
        pass

    def Control(self, request, context):
        TASK["OD"] = request.ObjectDetection
        TASK["HPT"] = request.HandPoseTracking
        TASK["PE"] = request.PoseEstimation
        print("Get request")

        response = control_pb2.ControlResponse()
        response.success = True

        return response


def gstreamer_camera(queue, stop_switch):
    # Use the provided pipeline to construct the video capture in opencv
    pipeline = (
        "nvarguscamerasrc ! "
            "video/x-raw(memory:NVMM), "
            "width=(int)1920, height=(int)1080, "
            "format=(string)NV12, framerate=(fraction)10/1 ! "
        "queue ! "
        "nvvidconv flip-method=2 ! "
            "video/x-raw, "
            "width=(int)1920, height=(int)1080, "
            "format=(string)BGRx, framerate=(fraction)10/1 ! "
        "videoconvert ! "
            "video/x-raw, format=(string)BGR ! "
        "appsink"
    )
    # Complete the function body
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    while True:
        if stop_switch.is_set():
            break
        try:
            ret, frame = cap.read()
            queue.put(frame)
        except:
            pass
    cap.release()


def gstreamer_rtmpstream(queue, stop_switch, task):
    # Use the provided pipeline to construct the video writer in opencv
    pipeline = (
        "appsrc ! "
            "video/x-raw, format=(string)BGR ! "
        "queue ! "
        "videoconvert ! "
            "video/x-raw, format=RGBA ! "
        "nvvidconv ! "
        "nvv4l2h264enc bitrate=8000000 ! "
        "h264parse ! "
        "flvmux ! "
        'rtmpsink location="rtmp://localhost/rtmp/live live=1"'
    )
    # Complete the function body
    # You can apply some simple computer vision algorithm here
    out = cv2.VideoWriter(pipeline, cv2.CAP_GSTREAMER, 0, fps, (width, height), True)
    while True:
        if stop_switch.is_set():
            break
        if not out.isOpened():
            print("Failed to open output")

        try:
            image = queue.get()
            if image is not None:
                # print(task)
                if task["OD"]:
                    with mdp_object_detection.ObjectDetection(
                        min_detection_confidence=0.1) as object_detection:

                        results = object_detection.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                        # results = object_detection.process(image)

                        if results.detections:
                            for detection in results.detections:
                                mdp_drawing.draw_detection(image, detection)

                if task["HPT"]:
                    with mdp_hands.Hands(
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5) as hands:

                        results = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                        # results = hands.process(image)
                        
                        if results.multi_hand_landmarks:
                            for hand_landmarks in results.multi_hand_landmarks:
                                mdp_drawing.draw_landmarks(
                                    image,
                                    hand_landmarks,
                                    mdp_hands.HAND_CONNECTIONS,
                                    mdp_drawing_styles.get_default_hand_landmarks_style(),
                                    mdp_drawing_styles.get_default_hand_connections_style())

                if task["PE"]:

                    with mdp_pose.Pose(
                        static_image_mode=False,
                        model_complexity=1,
                        enable_segmentation=True,
                        min_detection_confidence=0.5) as pose:

                        results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

                        if results.pose_landmarks:

                            mdp_drawing.draw_landmarks(
                                image,
                                results.pose_landmarks,
                                mdp_pose.POSE_CONNECTIONS,
                                landmark_drawing_spec=mdp_drawing_styles.get_default_pose_landmarks_style())


                out.write(image)
        except:
            pass

    out.release()


# Complelte the code
if __name__ == "__main__":

    manager = mp.Manager()
    TASK = manager.dict(lock=False)
    TASK["OD"] = False
    TASK["HPT"] = False
    TASK["PE"] = False

    # Access to gRPC server
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="0.0.0.0", type=str)
    parser.add_argument("--port", default=8080, type=int)
    args = vars(parser.parse_args())

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = ControlServicer()
    control_pb2_grpc.add_ControlServicer_to_server(servicer, server)

    server.add_insecure_port(f"{args['ip']}:{args['port']}")
    server.start()
    print(f"Run gRPC Server at {args['ip']}:{args['port']}")

    print("Setting streaming")
    queue = mp.Queue(maxsize=100)
    stop_switch = mp.Event()
    camera = mp.Process(target=gstreamer_camera, args=[queue, stop_switch])
    stream = mp.Process(target=gstreamer_rtmpstream, args=[queue, stop_switch, TASK])
    camera.start()
    stream.start()

    try:
        while True:
            if stop_switch.is_set():
                camera.terminate()
                stream.terminate()
        server.wait_for_termination()
    except KeyboardInterrupt as e:
        stop_switch.set()
        camera.terminate()
        stream.terminate()
