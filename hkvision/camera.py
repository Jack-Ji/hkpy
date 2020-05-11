# -*- coding: utf-8 -*-

import os
import time
import threading
from threading import Timer
import cv2
from . import api

class Camera:
    def __init__(self, ip, port, user, password, disconnect_cb = None, stoprecord_cb = None):
        self.inited = False
        self.userid, self.handle, self.playdata = api.login(ip, port, user, password)
        self.testing = False
        self.testthread = None
        self.recording = False
        self.recordfile = None
        self.maxrecordsize = None
        self.recordchecktime = time.time()
        self.timer = Timer(1, self.on_timer)
        self.timer.start()
        self.disconnect_cb = disconnect_cb
        self.stoprecord_cb = stoprecord_cb
        self.inited = True

    def __del__(self):
        if self.inited:
            # 停止镜头动作
            self.stop()

            # 销毁sdk相关资源
            api.stop(self.userid, self.handle, self.playdata[0])

            # 销毁定时器
            self.time.cancel()

    # 增加镜头变倍
    def zoom_in(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_ZOOM_IN)

    # 减小镜头变倍
    def zoom_out(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_ZOOM_OUT)

    # 镜头向上转动
    def move_up(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_UP)

    # 镜头向下转动
    def move_down(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_DOWN)

    # 镜头向左转动
    def move_left(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_LEFT)

    # 镜头向右转动
    def move_right(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_RIGHT)

    # 镜头停止转动/变倍
    def stop(self):
        api.ptz_basic_control(self.handle, api.PTZ_CMD_STOP)

    # 固定坐标控制
    def move_to(self, pan, tilt):
        api.ptz_set(self.userid, pan, tilt)

    # 获取当前坐标
    def get_pos(self):
        return api.ptz_get(self.userid)

    # 获取当前画面帧
    def get_frame(self):
        return self.playdata[1].pop()

    # 定时器回调
    def on_timer(self):
        try:
            if not self.recording:
                return
            recordsize = os.stat(self.recordfile).st_size
            if recordsize < self.maxrecordsize:
                return
            self.stop_record()
            if not self.disconnect_cb is None:
                self.stoprecord_cb()
        except Exception as e:
            print(e)
        finally:
            self.timer = Timer(1, self.on_timer)
            self.timer.start()

    # 录制文件，默认最大文件10GB
    # 成功返回True，失败返回False
    def start_record(self, path, maxsize=10*1024*1024*1024):
        if self.recording:
            raise RuntimeError("still recording")
        if api.start_record(self.handle, path):
            self.recording = True
            self.recordfile = path
            self.maxrecordsize = maxsize
            return True
        print("start record failed, code:", api.get_netsdk_error_code())
        return False

    # 停止录制
    def stop_record(self):
        if self.recording:
            api.stop_record(self.handle)
            self.recording = False
            self.recordfile = None

    # 开始测试抓图结果
    def start_test(self):

        def showimg():
            winname = '抓图结果'
            cv2.namedWindow(winname)
            while self.testing:
                try:
                    img = self.get_frame()
                    newsize = (img.shape[1]//4, img.shape[0]//4)
                    img = cv2.resize(img, newsize)
                    cv2.imshow(winname, img)
                    cv2.waitKey(1)
                except Exception as e:
                    time.sleep(0.01)
            cv2.destroyAllWindows()

        self.testing = True
        self.testthread = threading.Thread(target=showimg)
        self.testthread.start()

    # 停止测试
    def stop_test(self):
        self.testing = False
        self.testthread.join()
