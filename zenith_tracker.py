import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5 import QtCore


class ZenithTracker:

    def __init__(self, star_plot_widget):
        self.star_plot = star_plot_widget

        self.satellite_pos = (45.0, 30.0)

        self.tracker_angle = (0.0, 0.0)

        self.init_plot()

    def init_plot(self):
        self.figure = Figure(figsize=(4.21, 4.21), dpi=100)

        self.figure.patch.set_alpha(0.2)
        self.figure.patch.set_facecolor('white')

        self.figure.subplots_adjust(left=0.1, right=0.9, bottom=0.1, top=0.9)

        self.canvas = FigureCanvas(self.figure)

        self.canvas.setStyleSheet("background-color: transparent;")
        self.canvas.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.ax = self.figure.add_subplot(111, projection='polar')

        self.ax.patch.set_alpha(0.2)
        self.ax.patch.set_facecolor('white')

        if self.star_plot.layout():
            old_layout = self.star_plot.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)

        layout = QVBoxLayout(self.star_plot)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.update_plot()

    def update_plot(self):
        self.ax.clear()

        self.ax.patch.set_alpha(0.2)
        self.ax.patch.set_facecolor('white')

        self.ax.set_theta_zero_location('N')
        self.ax.set_theta_direction(-1)

        self.ax.set_xticks(np.radians([0, 45, 90, 135, 180, 225, 270, 315]))
        self.ax.set_xticklabels(['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'])

        self.ax.set_yticks([0.25, 0.5, 0.75])
        self.ax.set_yticklabels(['', '', ''])

        self.ax.set_ylim(0, 1)

        theta = np.linspace(0, 2 * np.pi, 100)
        self.ax.plot(theta, np.ones(100), 'gray', alpha=0.5, linewidth=1)

        for elev in [30, 60]:
            r = 1 - elev / 90.0
            self.ax.plot(theta, np.full_like(theta, r), 'lightgray',
                         alpha=0.4, linewidth=0.8, linestyle='--')

        sat_az_rad = np.radians(self.satellite_pos[0])
        sat_r = 1 - self.satellite_pos[1] / 90.0

        self.ax.scatter(sat_az_rad, sat_r,
                        s=120,
                        c='blue',
                        alpha=0.9,
                        edgecolors='darkblue',
                        linewidth=1.5,
                        zorder=10)

        track_az_rad = np.radians(self.tracker_angle[0])
        track_r = 1 - self.tracker_angle[1] / 90.0

        self.ax.scatter(track_az_rad, track_r,
                        s=80,
                        c='red',
                        alpha=0.9,
                        edgecolors='darkred',
                        linewidth=1.0,
                        zorder=11)

        for az in [self.satellite_pos[0], self.tracker_angle[0]]:
            rad = np.radians(az)
            self.ax.plot([rad, rad], [0, 0.97], 'gray',
                         alpha=0.4, linewidth=0.8, linestyle=':')

        self.ax.grid(True, alpha=0.4)

        self.canvas.draw()


    def set_satellite_position(self, azimuth, elevation):
        azimuth = azimuth % 360
        elevation = max(0, min(90, elevation))

        self.satellite_pos = (azimuth, elevation)
        self.update_plot()

    def set_tracker_angle(self, azimuth, elevation):
        azimuth = azimuth % 360
        elevation = max(0, min(90, elevation))

        self.tracker_angle = (azimuth, elevation)
        self.update_plot()

    def get_satellite_position(self):
        return self.satellite_pos

    def get_tracker_angle(self):
        return self.tracker_angle

    def get_angle_difference(self):
        az1, el1 = self.satellite_pos
        az2, el2 = self.tracker_angle

        az_diff = abs(az1 - az2)
        if az_diff > 180:
            az_diff = 360 - az_diff

        el_diff = abs(el1 - el2)
        return az_diff, el_diff

    def clear_plot(self):
        self.satellite_pos = (45.0, 30.0)
        self.tracker_angle = (0.0, 0.0)
        self.update_plot()