🛰️ 卫星天顶图追踪器 (ZenithTracker)

项目简介

这是一个基于 PyQt5 和 Matplotlib 的卫星天顶图可视化工具，用于实时显示卫星位置和地面追踪器的对准角度。

功能特点

· 🎯 双目标显示：蓝色圆点代表卫星，红色小圆点代表追踪器
· 🧭 极坐标显示：标准的极坐标天顶图，0°指向正北
· 📏 简洁界面：只保留必要的方位角标签和刻度线
· 🔄 实时更新：支持动态更新卫星和追踪器位置

安装依赖


pip install PyQt5 matplotlib numpy


快速使用

1. 在 Qt Designer 中设计界面

· 放置一个 QWidget，设置 objectName 为 star_plot
· 调整大小（推荐 421×421 像素）
· 保存为 .ui 文件并生成 UI.py

2. 主程序中使用


from UI import Ui_MainWindow
from zenith_tracker import ZenithTracker

class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # 1. 创建追踪器实例
        self.tracker = ZenithTracker(self.star_plot)

        # 2. 设置卫星位置
        self.tracker.set_satellite_position(azimuth=120, elevation=45)

        # 3. 设置追踪器角度
        self.tracker.set_tracker_angle(azimuth=115, elevation=43)


核心 API

ZenithTracker 类


# 创建实例
tracker = ZenithTracker(star_plot_widget)

# 设置卫星位置
tracker.set_satellite_position(azimuth, elevation)  # 方位角(0-360°), 仰角(0-90°)

# 设置追踪器角度
tracker.set_tracker_angle(azimuth, elevation)  # 方位角(0-360°), 仰角(0-90°)

# 获取当前位置
sat_pos = tracker.get_satellite_position()  # 返回 (azimuth, elevation)
track_pos = tracker.get_tracker_angle()     # 返回 (azimuth, elevation)

# 获取角度差
az_diff, el_diff = tracker.get_angle_difference()  # 返回方位差和仰角差
```

显示说明

· 蓝色圆点 (较大)：卫星当前位置
· 红色圆点 (较小)：追踪器对准角度
· 方位角标签：N, NE, E, SE, S, SW, W, NW
· 仰角刻度：只有刻度线，无文字标签
· 重叠显示：当两者位置接近时，红色追踪点会覆盖在蓝色卫星点上

项目结构


卫星追踪项目/
├── main.py              # 主程序
├── UI.py                # Qt Designer生成的界面
├── zenith_tracker.py    # 天顶图追踪器类
├── your_design.ui       # Qt Designer设计文件
└── requirements.txt     # 依赖包列表


实时更新示例


# 使用定时器实时更新
from PyQt5.QtCore import QTimer

class MainApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.tracker = ZenithTracker(self.star_plot)

        # 设置定时器，每100ms更新一次
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_positions)
        self.timer.start(100)

    def update_positions(self):
        # 从数据源获取最新位置
        sat_az, sat_el = get_satellite_data()
        track_az, track_el = get_tracker_data()

        # 更新显示
        self.tracker.set_satellite_position(sat_az, sat_el)
        self.tracker.set_tracker_angle(track_az, track_el)


注意事项

1. 确保 star_plot 控件在 Qt Designer 中的 objectName 正确
2. 角度值会自动规范化（方位角 0-360°，仰角 0-90°）
3. 图形会在每次调用 set_satellite_position() 或 set_tracker_angle() 时自动刷新

许可证

MIT License