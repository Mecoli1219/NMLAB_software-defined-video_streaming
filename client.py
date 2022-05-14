import os
import os.path as osp
import sys
BUILD_DIR = osp.join(osp.dirname(osp.abspath(__file__)), "build/service/")
sys.path.insert(0, BUILD_DIR)
import argparse

import grpc
import control_pb2
import control_pb2_grpc

variable = {
    'od': False,
    'hpt': False,
    'pe': False,
}

def printVariable():
    print("**********************************************")
    print('Current Effect:')
    print('\tObject Detection:\t%s' % variable["od"])
    print('\tHand Pose Tracking:\t%s' % variable["hpt"])
    print('\tPose Estimation:\t%s' % variable["pe"])
    print("**********************************************")

def main(args):
    host = f"{args['ip']}:{args['port']}"
    # print(host)

    while True:
        ipt = input("Enter Command:")
        if ipt[0] == '+':
            if ipt[1:] in variable:
                variable[ipt[1:]] = True
            else:
                print("Error Command")
                continue
        elif ipt[0] == '-':
            if ipt[1:] in variable:
                variable[ipt[1:]] = False
            else:
                print("Error Command")
                continue
        elif ipt == "q":
            print("Quit")
            break
        else:
            print("Error Command")
            continue
        printVariable()

        try:
            with grpc.insecure_channel(host) as channel:
                stub = control_pb2_grpc.ControlStub(channel)

                request = control_pb2.ControlRequest()
                request.ObjectDetection = variable['od']
                request.HandPoseTracking = variable['hpt']
                request.PoseEstimation = variable['pe']
                # print(request)

                response = stub.Control(request)
                print(response.success)
        except:
            print("Error occur when sending to server")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=8080)
    # parser.add_argument("--od", type=bool, default=False)
    # parser.add_argument("--hpt", type=bool, default=False)
    # parser.add_argument("--pe", type=bool, default=False)
    
    args = vars(parser.parse_args())
    main(args)
