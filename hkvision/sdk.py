# -*- coding: utf-8 -*-

from ctypes import *
from .exception_handler import excallback

class _Protect:
    instance = None

# 检查是否已经初始化过
if _Protect.instance:
    raise RuntimeError("重复初始化SDK")

# 网络设备SDK初始化
netsdk = cdll.LoadLibrary('./libhcnetsdk.so')
rc = netsdk.NET_DVR_Init()
if rc != 1:
    raise RuntimeError('网络设备SDK初始化失败')

# 设置日志输出路径
rc = netsdk.NET_DVR_SetLogToFile(3, b"SDKLOG", 1)
if rc != 1:
    raise RuntimeError('设置日志输出失路径败')

# 设置异常通知回调
rc = netsdk.NET_DVR_SetExceptionCallBack_V30(0, None, excallback, None)
if rc != 1:
    raise RuntimeError('设置异常回调函数失败')

# 设置连接超时时间和尝试次数
rc = netsdk.NET_DVR_SetConnectTime(3000, 10)
if rc != 1:
    raise RuntimeError('设置连接超时时间和尝试次数失败')

# 设置自动重连
rc = netsdk.NET_DVR_SetReconnect(5000, 1)
if rc != 1:
    raise RuntimeError('设置自动重连失败')

# 设置回放录像不切片
class SDKLocalGeneralCFG(Structure):
    _fields_ = [("whatever1", c_byte),
                ("not_split_recordfile", c_byte),
                ("whatever2", c_byte),
                ("whatever3", c_byte),
                ("whatever4", c_byte*4),
                ("filesize", c_ulonglong),
                ("whatever6", c_uint),
                ("whatever7", c_byte),
                ("whatever8", c_byte),
                ("whatever9", c_byte*234)]

cfg = SDKLocalGeneralCFG()
cfg.not_split_recordfile = 1
rc = netsdk.NET_DVR_SetSDKLocalCfg(17, byref(cfg))
if rc != 1:
    raise RuntimeError('设置录像文件不切片失败')

# 播放控制SDK初始化
playsdk = cdll.LoadLibrary('./libPlayCtrl.so')

# 初始化结束
_Protect.instance = True
