Orbitron DDE 数据读取与解析模块
1. 程序逻辑
2. 安装要求
3. 快速开始
4. 详细使用方法
5. 输出数据格式详解
6. 错误处理
7. 示例应用

程序逻辑

1. 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Orbitron      │◄──►│   DDE 通信层    │◄──►│   OrbitronDDE   │
│   软件进程      │    │   (pywin32)     │    │     模块        │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                        │
                                                        ▼
                                                 ┌─────────────────┐
                                                 │   数据处理层    │
                                                 │  (OrbitronParser)│
                                                 └────────┬────────┘
                                                        │
                                                        ▼
                                                 ┌─────────────────┐
                                                 │   应用层        │
                                                 │       │
                                                 └─────────────────┘
```

2. 数据流逻辑

```
开始
  │
  ▼
1. 建立 DDE 连接
  │  ├─ 服务名: "Orbitron"
  │  └─ 主题名: "Tracking"
  │
  ▼
2. 请求两种格式数据
  │  ├─ TrackingDataEx: 扩展格式数据
  │  └─ TrackingData:   标准格式数据
  │
  ▼
3. 解析原始数据
  │  ├─ 方法1: 正则表达式精确匹配
  │  ├─ 方法2: 备用解析逻辑
  │  └─ 错误处理与容错
  │
  ▼
4. 格式化输出
  │  ├─ 数值类型转换
  │  ├─ 单位标准化
  │  └─ 数据结构化
  │
  ▼
5. 回调通知
  │  └─ 触发用户注册的回调函数
  │
  ▼
6. 存储当前状态
  └─ 供同步查询使用
```

3. 解析算法

3.1 TrackingDataEx 解析（主要方法）

```python
# 原始数据示例：SN"ISS" AZ234.4 EL-64.7 DN130168053 UP121749014
# 解析步骤：
# 1. 使用正则模式：r'(\w+)(?:"([^"]*)"|([^"\s]+))?'
# 2. 匹配结果：[('SN', 'ISS', ''), ('AZ', '', '234.4'), ('EL', '', '-64.7'), ...]
# 3. 根据字段类型转换：
#    - AZ/EL/RA/RR/LO/LA/AL → float
#    - DN/UP → int (频率值)
#    - SN/UM/DM/AOS → str
#    - TU/TL → str (时间字符串)
```

3.2 TrackingData 解析（备用方法）

```python
# 原始数据示例：SNISS AZ234.4 EL-64.7 DN130168053 UP121749014
# 解析步骤：
# 1. 按空格分割：['SNISS', 'AZ234.4', 'EL-64.7', 'DN130168053', ...]
# 2. 根据前缀提取数据：
#    - SN前缀: 卫星名称
#    - AZ前缀: 方位角 (float)
#    - EL前缀: 仰角 (float)
#    - DN前缀: 下行频率 (int)
#    - UP前缀: 上行频率 (int)
```

4. 线程模型

```
主线程 (您的应用)
  │
  ├── 同步调用
  │     ├─ connect()          # 建立连接
  │     ├─ read_data()        # 读取数据
  │     ├─ get_satellite_info() # 获取信息
  │     └─ disconnect()       # 断开连接
  │
  └── 异步监控
        │
        ▼
    监控线程 (内部)
        │
        ▼
    循环执行：
    1. read_data()           # 读取数据
    2. 触发回调函数           # 通知更新
    3. sleep(interval)       # 等待间隔
    4. 检查停止标志
```

安装要求

系统要求

· Windows 操作系统（必需，因为使用 DDE）
· Python 3.6 或更高版本
· Orbitron 软件（已安装并运行）

Python 依赖

```bash
# 必需依赖
pip install pywin32

# 可选依赖（用于扩展功能）
pip install pyserial    # 串口控制
pip install numpy       # 数值计算
pip install matplotlib  # 数据可视化
```

Orbitron 设置

1. 确保 Orbitron 正在运行
2. 在 Orbitron 中选择并开始跟踪卫星
3. 确保 DDE 服务器已启用（Orbitron 默认启用）

快速开始

基本使用

```python
from orbitron_module import OrbitronDDE

# 创建连接实例
orbitron = OrbitronDDE()

# 连接到 Orbitron
if orbitron.connect():
    # 读取一次数据
    data = orbitron.read_data()
    print(f"卫星: {data['tracking_data_ex'].get('sn', '未知')}")

    # 断开连接
    orbitron.disconnect()
```

快速函数

```python
from orbitron_module import get_orbitron_data

# 一键获取卫星信息
info = get_orbitron_data()
if info['status'] == 'tracking':
    print(f"{info['satellite']}: 方位 {info['azimuth']:.1f}°, 仰角 {info['elevation']:.1f}°")
```

详细使用方法

1. 创建实例

```python
# 默认参数（适用于大多数情况）
orbitron = OrbitronDDE()

# 自定义服务名和主题名
orbitron = OrbitronDDE(service="Orbitron", topic="Tracking")
```

2. 连接管理

```python
# 手动连接
success = orbitron.connect()
if success:
    print("连接成功")
else:
    print("连接失败，请检查 Orbitron 是否运行")

# 使用上下文管理器（推荐）
with OrbitronDDE() as orbitron:
    # 在此代码块内自动连接
    data = orbitron.read_data()
    # 退出代码块时自动断开

# 检查连接状态
if orbitron.is_connected:
    print("已连接到 Orbitron")
```

3. 数据读取方式

方式A：同步读取（按需获取）

```python
# 读取完整数据（包含两种格式）
full_data = orbitron.read_data()
"""
full_data 结构:
{
    "status": "success"|"error"|"disconnected",
    "timestamp": 1633024567.891,
    "tracking_data_ex": {...},  # TrackingDataEx 解析结果
    "tracking_data": {...},     # TrackingData 解析结果
    "error": "错误信息"          # 仅当 status="error" 时存在
}
"""

# 读取简化信息（推荐）
simple_info = orbitron.get_satellite_info()
"""
simple_info 结构:
{
    "status": "tracking"|"no_tracking"|"error",
    "satellite": "ISS",
    "azimuth": 234.5,
    "elevation": -64.7,
    "uplink_freq": 145990000,
    "downlink_freq": 437800000,
    "range": 1350.2,           # 可选，仅当 TrackingDataEx 中有 RA 字段时
    "range_rate": -7.42,       # 可选，仅当 TrackingDataEx 中有 RR 字段时
    "timestamp": 1633024567.891
}
"""
```

方式B：异步监控（实时更新）

```python
# 定义回调函数
def on_new_data(data):
    """数据更新时的处理函数"""
    if data["tracking_data_ex"]:
        sat_info = data["tracking_data_ex"]
        if sat_info.get("status") == "tracking":
            print(f"更新: {sat_info.get('sn')} - "
                  f"AZ: {sat_info.get('az', 0):.1f}°, "
                  f"EL: {sat_info.get('el', 0):.1f}°")

# 添加回调
orbitron.add_callback(on_new_data)

# 开始后台监控（每2秒更新一次）
orbitron.start_monitoring(interval=2.0)

# 运行一段时间...
import time
time.sleep(30)  # 监控30秒

# 停止监控
orbitron.stop_monitoring()

# 可以添加多个回调函数
def log_data(data):
    with open("orbitron_log.txt", "a") as f:
        f.write(f"{time.time()}: {data}\n")

orbitron.add_callback(log_data)
```

4. 错误处理

```python
try:
    with OrbitronDDE() as orbitron:
        data = orbitron.read_data()

        if data["status"] == "success":
            # 处理成功数据
            pass
        elif data["status"] == "error":
            print(f"读取错误: {data.get('error')}")
        elif data["status"] == "disconnected":
            print("未连接到 Orbitron")

except Exception as e:
    print(f"程序异常: {e}")
```

5. 高级用法

数据持久化

```python
import json
from datetime import datetime

class OrbitronRecorder:
    def __init__(self, orbitron: OrbitronDDE):
        self.orbitron = orbitron
        self.data_log = []

    def start_recording(self):
        def record_callback(data):
            record = {
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            self.data_log.append(record)

        self.orbitron.add_callback(record_callback)
        self.orbitron.start_monitoring(interval=1)

    def save_to_file(self, filename="orbitron_data.json"):
        with open(filename, "w") as f:
            json.dump(self.data_log, f, indent=2)
```

多线程集成

```python
import threading
import queue

class OrbitronDataQueue:
    def __init__(self):
        self.data_queue = queue.Queue()
        self.orbitron = OrbitronDDE()

    def start(self):
        # 定义队列回调
        def queue_callback(data):
            self.data_queue.put(data)

        # 连接并开始监控
        if self.orbitron.connect():
            self.orbitron.add_callback(queue_callback)
            self.orbitron.start_monitoring(interval=1)

    def get_latest(self, timeout=1):
        """获取最新数据（非阻塞）"""
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None
```

输出数据格式详解

1. read_data() 返回的完整数据结构

```python
{
    # 操作状态
    "status": "success",           # 可能值: "success", "error", "disconnected"

    # 时间戳（Unix 时间戳，秒.毫秒）
    "timestamp": 1633024567.891235,

    # TrackingDataEx 解析结果（扩展格式）
    "tracking_data_ex": {
        "status": "tracking",      # 可能值: "tracking", "no_data", "parse_error"
        "raw": "SN\"ISS\" AZ234.4 EL-64.7 DN130168053 UP121749014 RA1350.2 RR-7.42",
        "errors": [],              # 解析错误列表（如有）

        # 卫星基本信息
        "sn": "ISS",               # 卫星名称 (Satellite Name)

        # 位置信息
        "az": 234.4,               # 方位角 (Azimuth)，单位：度
        "el": -64.7,               # 仰角 (Elevation)，单位：度

        # 频率信息
        "dn_freq": 130168053,      # 下行频率 (Downlink Frequency)，单位：Hz
        "up_freq": 121749014,      # 上行频率 (Uplink Frequency)，单位：Hz

        # 扩展信息（如有）
        "ra": 1350.2,              # 距离 (Range)，单位：km
        "rr": -7.42,               # 距离变化率 (Range Rate)，单位：km/s

        # 调制方式
        "dm": "FM",                # 下行调制 (Downlink Modulation)
        "um": "FM",                # 上行调制 (Uplink Modulation)

        # 位置信息
        "lo": -74.0059,            # 观测站经度 (Longitude)
        "la": 40.7128,             # 观测站纬度 (Latitude)
        "al": 10.0,                # 观测站海拔 (Altitude)，单位：m

        # 时间信息
        "tu_time": "12:34:56",     # 下次升交时间 (Time Until AOS)
        "tl_time": "13:45:12",     # 跟踪剩余时间 (Time Left)

        # 事件信息
        "aos": "12:34:56",         # 升交时间 (Acquisition of Signal)

        # 其他可能字段（根据 Orbitron 输出）
        "...": "..."
    },

    # TrackingData 解析结果（标准格式）
    "tracking_data": {
        "status": "tracking",
        "raw": "SNISS AZ234.4 EL-64.7 DN130168053 UP121749014",

        # 核心字段（同 TrackingDataEx，但可能不全）
        "sn": "ISS",
        "az": 234.4,
        "el": -64.7,
        "dn_freq": 130168053,
        "up_freq": 121749014,
        "dm": "FM",     # 可能不存在
        "um": "FM",     # 可能不存在
        "error": ""     # 仅当 status="parse_error" 时存在
    },

    # 错误信息（仅当 status="error" 时存在）
    "error": "DDE 请求失败"
}
```

2. get_satellite_info() 返回的简化结构

```python
{
    # 跟踪状态
    "status": "tracking",          # 可能值: "tracking", "no_tracking", "error"

    # 卫星标识
    "satellite": "ISS (ZARYA)",

    # 位置数据
    "azimuth": 234.5,              # 方位角，范围: 0° ~ 360°，精度: 0.1°
    "elevation": -64.7,            # 仰角，范围: -90° ~ 90°，精度: 0.1°

    # 频率数据（单位：Hz）
    "uplink_freq": 145990000,      # 典型值: 144-146 MHz (VHF), 430-440 MHz (UHF)
    "downlink_freq": 437800000,

    # 距离信息（如有）
    "range": 1350.2,               # 距离，单位: km，精度: 0.1 km
    "range_rate": -7.42,           # 距离变化率，单位: km/s，精度: 0.01 km/s

    # 时间戳
    "timestamp": 1633024567.891    # Unix 时间戳，秒.毫秒
}
```

3. 原始数据格式说明

TrackingDataEx 格式

```
SN"卫星名称" AZ方位角 EL仰角 DN下行频率 UP上行频率 RA距离 RR距离变化率 DM下行调制 UM上行调制 LO经度 LA纬度 AL海拔 TU下次升交时间 TL跟踪剩余时间 AOS升交时间
```

示例数据：

```
SN"ISS (ZARYA)" AZ234.4 EL-64.7 DN130168053 UP121749014 RA1350.2 RR-7.42 DMFM UMFM LO-74.0059 LA40.7128 AL10.0 TU00:12:34 TL00:45:12 AOS12:34:56
```

字段详解：

字段 全称 说明 格式 示例
SN Satellite Name 卫星名称 引号包裹字符串 "ISS (ZARYA)"
AZ Azimuth 方位角 浮点数，单位：度 234.4
EL Elevation 仰角 浮点数，单位：度 -64.7
DN Downlink Frequency 下行频率 整数，单位：Hz 130168053
UP Uplink Frequency 上行频率 整数，单位：Hz 121749014
RA Range 距离 浮点数，单位：km 1350.2
RR Range Rate 距离变化率 浮点数，单位：km/s -7.42
DM Downlink Modulation 下行调制 字符串 "FM"
UM Uplink Modulation 上行调制 字符串 "FM"
LO Longitude 观测站经度 浮点数，单位：度 -74.0059
LA Latitude 观测站纬度 浮点数，单位：度 40.7128
AL Altitude 观测站海拔 浮点数，单位：米 10.0
TU Time Until AOS 下次升交时间 时间字符串 "00:12:34"
TL Time Left 跟踪剩余时间 时间字符串 "00:45:12"
AOS Acquisition of Signal 升交时间 时间字符串 "12:34:56"

空格规则：

· 字段之间用一个空格分隔
· 字段名与值之间没有空格
· 字符串值用双引号包裹，引号内可以有空格
· 数值值直接跟在字段名后，没有引号

TrackingData 格式

```
SN卫星名称 AZ方位角 EL仰角 DN下行频率 UP上行频率 DM下行调制 UM上行调制
```

示例数据：

```
SNISS AZ234.4 EL-64.7 DN130168053 UP121749014 DMFM UMFM
```

与 TrackingDataEx 的区别：

1. 卫星名称没有引号：SNISS 而不是 SN"ISS"
2. 字段较少：缺少 RA、RR、LO、LA、AL、TU、TL、AOS 等扩展字段
3. 没有字符串分隔：所有值直接跟在字段名后

4. 数据类型转换规则

数值字段

字段 类型 转换规则 示例输入 解析结果
AZ, EL, RA, RR float float(value) AZ234.4 234.4
LO, LA, AL float float(value) LO-74.0059 -74.0059
DN, UP int int(float(value)) DN130168053 130168053

字符串字段

字段 转换规则 示例输入 解析结果
SN, DM, UM, AOS 直接使用 SN"ISS" "ISS"
TU, TL 作为字符串 TU00:12:34 "00:12:34"

5. 错误数据格式

无数据情况

```python
{
    "status": "no_data",
    "raw": "",                    # 空字符串
    "errors": []                  # 空列表
}
```

解析错误

```python
{
    "status": "parse_error",
    "raw": "SN ISS AZinvalid EL-64.7",  # 原始错误数据
    "errors": [
        "字段 AZ 值转换失败: invalid",
        "解析异常: could not convert string to float: 'invalid'"
    ]
}
```

连接错误

```python
{
    "status": "disconnected",
    "error": "未连接到 Orbitron"
}
```

错误处理

常见错误及解决方案

1. 连接失败

```python
# 错误信息: "无法连接到 Orbitron"
# 可能原因:
#   - Orbitron 未运行
#   - DDE 服务未启用
#   - 权限不足
# 解决方案:
#   1. 确保 Orbitron 正在运行
#   2. 在 Orbitron 中检查 DDE 设置
#   3. 以管理员身份运行 Python
```

2. 数据解析错误

```python
# 错误信息: "字段 AZ 值转换失败: invalid"
# 可能原因:
#   - Orbitron 输出格式异常
#   - 数据不完整
# 解决方案:
#   1. 检查 Orbitron 跟踪状态
#   2. 使用备用解析模式
#   3. 增加错误重试机制
```

3. 频率数据异常

```python
# 现象: 频率值为 0 或非常大
# 可能原因:
#   - 卫星未设置频率
#   - Orbitron 配置错误
# 解决方案:
#   1. 在 Orbitron 中检查卫星频率设置
#   2. 使用默认频率或从数据库获取
```

错误处理最佳实践

```python
from orbitron_module import OrbitronDDE

class RobustOrbitronReader:
    def __init__(self, max_retries=3):
        self.orbitron = OrbitronDDE()
        self.max_retries = max_retries

    def get_data_with_retry(self):
        """带重试的数据获取"""
        for attempt in range(self.max_retries):
            try:
                if not self.orbitron.is_connected:
                    if not self.orbitron.connect():
                        time.sleep(1)
                        continue

                data = self.orbitron.read_data()

                if data["status"] == "success":
                    return data
                elif data["status"] == "error":
                    print(f"尝试 {attempt+1} 失败: {data.get('error')}")

                time.sleep(0.5)  # 等待后重试

            except Exception as e:
                print(f"尝试 {attempt+1} 异常: {e}")
                time.sleep(1)

        return {"status": "max_retries_exceeded"}
```

示例应用

1. 简易卫星跟踪显示器

```python
from orbitron_module import OrbitronDDE
import time

def simple_tracker():
    """简易卫星跟踪显示器"""
    with OrbitronDDE() as orbitron:
        orbitron.start_monitoring(interval=1)

        def display_callback(data):
            if data["tracking_data_ex"]:
                info = data["tracking_data_ex"]
                if info.get("status") == "tracking":
                    print(f"\r卫星: {info.get('sn', '未知'):15} "
                          f"方位: {info.get('az', 0):6.1f}° "
                          f"仰角: {info.get('el', 0):6.1f}° "
                          f"距离: {info.get('ra', 0):7.1f}km", end="")

        orbitron.add_callback(display_callback)
        time.sleep(60)  # 显示60秒

if __name__ == "__main__":
    simple_tracker()
```

2. 数据记录器

```python
import csv
from datetime import datetime
from orbitron_module import OrbitronDDE

class OrbitronLogger:
    def __init__(self, filename="satellite_log.csv"):
        self.filename = filename
        self.orbitron = OrbitronDDE()
        self.setup_csv()

    def setup_csv(self):
        """设置 CSV 文件头"""
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'satellite', 'azimuth', 'elevation',
                'uplink_freq', 'downlink_freq', 'range', 'range_rate'
            ])

    def start_logging(self, interval=1, duration=3600):
        """开始记录数据"""
        if self.orbitron.connect():
            start_time = time.time()

            while time.time() - start_time < duration:
                info = self.orbitron.get_satellite_info()

                if info['status'] == 'tracking':
                    with open(self.filename, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.now().isoformat(),
                            info['satellite'],
                            info['azimuth'],
                            info['elevation'],
                            info['uplink_freq'],
                            info['downlink_freq'],
                            info.get('range', 0),
                            info.get('range_rate', 0)
                        ])

                time.sleep(interval)

            self.orbitron.disconnect()
```

3. Web API 服务

```python
from flask import Flask, jsonify
from orbitron_module import OrbitronDDE
import threading

app = Flask(__name__)
orbitron = OrbitronDDE()
latest_data = {}

def update_data():
    """后台更新数据"""
    global latest_data
    if orbitron.connect():
        orbitron.start_monitoring(interval=1)

        def callback(data):
            global latest_data
            latest_data = data

        orbitron.add_callback(callback)

# 启动后台更新线程
update_thread = threading.Thread(target=update_data, daemon=True)
update_thread.start()

@app.route('/api/satellite/status')
def get_status():
    """获取卫星状态 API"""
    return jsonify(latest_data.get('tracking_data_ex', {}))

@app.route('/api/satellite/simple')
def get_simple():
    """获取简化信息 API"""
    info = orbitron.get_satellite_info()
    return jsonify(info)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```




!!!:
更新：仅get_orbitron_data()可用,且一般需求强烈使用该函数
OrbitronDDE 类 不可用
