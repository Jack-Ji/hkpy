# -*- coding: utf-8 -*-

from ctypes import *
import time
from collections import deque
import numpy as np
import cv2
from .sdk import *

MAX_QLEN = 5

# 获取netsdk调用错误玛
def get_netsdk_error_code():
    return netsdk.NET_DVR_GetLastError()
# 获取playsdk调用错误码
def get_playsdk_error_code(port):
    return playsdk.PlayM4_GetLastError(port)

# 设备登录
class DeviceInfoV30(Structure):
    _fields_ = [("whatever1", c_byte*48),
                ("whatever2", c_byte),
                ("whatever3", c_byte),
                ("whatever4", c_byte),
                ("whatever5", c_byte), ("whatever6", c_byte),
                ("analog_channel", c_byte),
                ("whatever8", c_byte),
                ("whatever9", c_byte),
                ("whatever10", c_byte),
                ("whatever11", c_byte),
                ("whatever12", c_byte),
                ("whatever13", c_byte),
                ("whatever14", c_byte),
                ("whatever15", c_byte),
                ("whatever16", c_ushort),
                ("whatever17", c_byte),
                ("whatever18", c_byte),
                ("digital_channel", c_byte),
                ("whatever20", c_byte),
                ("whatever21", c_byte),
                ("whatever22", c_byte),
                ("whatever23", c_byte),
                ("whatever24", c_byte),
                ("whatever25", c_byte),
                ("whatever26", c_byte),
                ("whatever27", c_byte),
                ("whatever28", c_byte),
                ("whatever29", c_ushort),
                ("whatever30", c_byte),
                ("whatever31", c_byte)]

class DeviceInfoV40(Structure):
    _fields_ = [("v30", DeviceInfoV30),
                ("support_lock", c_byte),
                ("retry_login_time", c_byte),
                ("password_level", c_byte),
                ("proxy_type", c_byte),
                ("lock_time", c_uint),
                ("char_encode_type", c_byte),
                ("support_dev5", c_byte),
                ("support", c_byte),
                ("login_mode", c_byte),
                ("oem_code", c_uint),
                ("residual_validity1", c_int),
                ("residual_validity2", c_byte),
                ("res", c_byte*243)]

class LoginInfo(Structure):
    _fields_ = [("ip", c_char*129),
                ("use_transport", c_byte),
                ("port", c_ushort),
                ("user", c_char*64),
                ("password", c_char*64),
                ("logincallback", CFUNCTYPE(None, c_int, c_uint, POINTER(DeviceInfoV40), c_void_p)),
                ("user_data", c_void_p),
                ("async_login", c_int),
                ("proxy_type", c_byte),
                ("utc_time", c_byte),
                ("login_mode", c_byte),
                ("https", c_byte),
                ("proxyid", c_int),
                ("verify_mode", c_byte),
                ("res", c_byte*119)]

class PreviewInfo(Structure):
    _fields_ = [("channel", c_int),
                ("stream_type", c_uint),
                ("link_mode", c_int),
                ("play_win", c_uint),
                ("blocked", c_uint),
                ("passback_record", c_uint),
                ("preview_mode", c_byte),
                ("stream_id", c_byte*32),
                ("proto_type", c_byte),
                ("res1", c_byte),
                ("video_coding_type", c_byte),
                ("display_buf_num", c_uint),
                ("npq_mode", c_byte),
                ("res2", c_byte*215)]

class FrameInfo(Structure):
    _fields_ = [("width", c_int),
                ("height", c_uint),
                ("stamp", c_int),
                ("type", c_int),
                ("rate", c_int),
                ("num", c_uint)]

# 抓图回调函数
@CFUNCTYPE(None, c_int, POINTER(c_byte), c_int, POINTER(FrameInfo), py_object, c_int)
def on_picture(port, buf, size, frame_info, queue, reserved):
    # 转换yv12至rgb格式并添加至队列
    # 参考https://stackoverflow.com/questions/18737842/creating-a-mat-object-from-a-yv12-image-buffer/55758336#55758336
    finfo = frame_info[0]
    yv12img = np.ctypeslib.as_array(buf, (finfo.height*3//2, finfo.width))
    yv12img.dtype = np.uint8
    rgbimg = cv2.cvtColor(yv12img, cv2.COLOR_YUV2RGB_YV12)
    queue.append(rgbimg)

    #print("size:%d scale:%d/%d stamp:%d type:%d fps:%d num:%d" % 
    #        (size, finfo.width, finfo.height, finfo.stamp, finfo.type, finfo.rate, finfo.num))

# 码流回调函数
playfunc = playsdk.PlayM4_InputData
playfunc.argtypes = [c_int, POINTER(c_byte), c_uint]
@CFUNCTYPE(None, c_int, c_uint, POINTER(c_byte), c_uint, py_object)
def on_stream(handle, datatype, buf, size, userdata):
    if size == 0:
        return

    playport, queue = userdata
    if datatype == 1:
        # 分配播放通道号
        rc = playsdk.PlayM4_GetPort(byref(playport))
        if rc == 0:
            raise RuntimeError("播放SDK初始化失败")

        # 设置实时流媒体播放模式
        rc = playsdk.PlayM4_SetStreamOpenMode(playport, 0)
        if rc == 0:
            raise RuntimeError("设置实时流媒体模式失败", get_playsdk_error_code(playport))

        # 打开流
        fn = playsdk.PlayM4_OpenStream
        fn.argtypes = [c_int, POINTER(c_byte), c_uint, c_uint]
        rc = fn(playport, None, 0, 6*1024*1024)
        if rc == 0:
            raise RuntimeError("打开流失败", get_playsdk_error_code(playport))

        # 注册抓图回调函数
        fn = playsdk.PlayM4_SetDecCallBackMend
        fn.argtypes = [c_int, CFUNCTYPE(None, c_int, POINTER(c_byte), c_int, POINTER(FrameInfo), py_object, c_int), py_object]
        rc = fn(playport, on_picture, queue)
        if rc == 0:
            raise RuntimeError("设置抓图回调失败", get_playsdk_error_code(playport))

        # 打开视频解码
        fn = playsdk.PlayM4_Play
        fn.argtypes = [c_int, c_uint]
        rc = fn(playport, 0)
        if rc == 0:
            raise RuntimeError("开启播放失败", get_playsdk_error_code(playport))

    elif datatype == 2:
        # 输入并解码
        rc = playfunc(playport, buf, size)
        while rc == 0:
            time.sleep(0.01)
            rc =  playfunc(playport, buf, size)
    else:
        pass
    
def login(ip, port, user, password):
    """登录设备并返回控制句柄

        ip: 设备IP地址
        port: 设备监听端口
        user: 用户名
        password: 密码

        返回值: (用户ID, 控制句柄, (播放通道, 抓图结果))
    """

    # 登录设备
    fn = netsdk.NET_DVR_Login_V40
    fn.argtypes = [POINTER(LoginInfo), POINTER(DeviceInfoV40)]
    login_info = LoginInfo()
    login_info.ip = ip.encode()
    login_info.port = port
    login_info.user = user.encode()
    login_info.password = password.encode()
    device_info = DeviceInfoV40()
    user_id = fn(byref(login_info), byref(device_info))
    if user_id < 0:
        raise RuntimeError("用户登录失败", get_netsdk_error_code())

    # 开始预览
    playdata = (c_int(-1), deque(maxlen=MAX_QLEN))
    fn = netsdk.NET_DVR_RealPlay_V40
    fn.argtypes = [c_int, POINTER(PreviewInfo), CFUNCTYPE(None, c_int, c_uint, POINTER(c_byte), c_uint, py_object), py_object]
    preview_info = PreviewInfo()
    preview_info.channel = 1
    handle = fn(user_id, byref(preview_info), on_stream, playdata)
    if handle < 0:
        raise RuntimeError("预览失败", get_netsdk_error_code())

    return user_id, handle, playdata

# 停止解码和预览
def stop(userid, handle, playport):
    # 停止预览
    netsdk.NET_DVR_StopRealPlay(handle)

    # 停止解码
    playsdk.PlayM4_Stop(playport)
    playsdk.PlayM4_CloseStream(playport)
    playsdk.PlayM4_FreePort(playport)

    # 注销用户
    netsdk.NET_DVR_Logout(userid)

# PTZ基本控制
PTZ_CMD_STOP = 1
PTZ_CMD_UP = 2
PTZ_CMD_DOWN = 3
PTZ_CMD_LEFT = 4
PTZ_CMD_RIGHT = 5
PTZ_CMD_ZOOM_IN = 6
PTZ_CMD_ZOOM_OUT = 7

def ptz_basic_control(handle, cmd, speed=3):
    """控制镜头

        handle: 控制句柄
        cmd: 控制命令

        返回值: 0表示失败，1表示成功
    """

    # 提取接口
    fn = netsdk.NET_DVR_PTZControlWithSpeed
    fn.argtypes = [c_int, c_uint, c_uint]

    # 调用接口
    stop = 0
    if cmd == PTZ_CMD_STOP:
        stop = 1
        realcmd = 21
    elif cmd == PTZ_CMD_UP:
        realcmd = 21
    elif cmd == PTZ_CMD_DOWN:
        realcmd = 22
    elif cmd == PTZ_CMD_LEFT:
        realcmd = 23
    elif cmd == PTZ_CMD_RIGHT:
        realcmd = 24
    elif cmd == PTZ_CMD_ZOOM_IN:
        realcmd = 11
    elif cmd == PTZ_CMD_ZOOM_OUT:
        realcmd = 12
    else:
        raise RuntimeError("非法控制参数", get_netsdk_error_code())

    fn(handle, realcmd, stop, speed)

class PTZPos(Structure):
    _fields_ = [("action", c_ushort),
                ("pan", c_ushort),
                ("tilt", c_ushort),
                ("zoom", c_ushort)]

# PTZ高级设置
def ptz_set(userid, pan, tilt):
    if pan < 0 or pan > 360:
        raise RuntimeError("invalid pan")
    if tilt < 0 or tilt > 60:
        raise RuntimeError("invalid tilt")
    pos = PTZPos()
    pos.action = 5
    pos.pan = int(f'0x{pan}0', 16)
    pos.tilt = int(f'0x{tilt}0', 16)
    netsdk.NET_DVR_SetDVRConfig(userid, 292, 1, byref(pos), sizeof(pos))

# PTZ状态获取
def ptz_get(userid):
    pos = PTZPos()
    rsize = c_uint()
    netsdk.NET_DVR_GetDVRConfig(userid, 293, 1, byref(pos), sizeof(pos), byref(rsize))
    pan = int(f'{pos.pan:x}')//10
    tilt = int(f'{pos.tilt:x}')//10
    return pan, tilt

# 录像
def start_record(handler, path):
    return netsdk.NET_DVR_SaveRealData(handler, c_char_p(path.encode()))

# 停止录像
def stop_record(handler):
    netsdk.NET_DVR_StopSaveRealData(handler)
