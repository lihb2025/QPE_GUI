import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QComboBox, QLineEdit, QAction, QGroupBox, QStatusBar
)
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from visualization.plotter import plot_radar_data, create_map_features_on_ax
import cartopy.crs as ccrs
from iodata.read_radar import load_radar_via_dialog


class RadarViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X波段雷达基数据可视化软件")
        self.setWindowIcon(QIcon(r"C:\Users\lihb\PycharmProjects\QPE_GUI\resources\radar.ico"))
        self.resize(1100, 650)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 主界面布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # 雷达对象占位
        self.radar = None
        self.radar_file = None

        # 当前 ax
        self.ax = None

        # 地图要素缓存
        self.map_features = []
        self.map_visible = False

        # shapefile 路径
        self.county_shp = r"C:\Users\lihb\PycharmProjects\QPE_GUI\resources\ZA702_BOUL.shp"

        # 交互状态
        self._is_panning = False
        self._pan_start = None
        self._pan_extent = None
        self._mouse_cid = None
        self._press_cid = None
        self._release_cid = None
        self._motion_cid = None
        self._scroll_cid = None

        # 菜单栏
        self.create_menu_bar()

        # 绘图占位
        self.left_panel = None
        self.canvas = None

    # ---------------------- 菜单栏 ----------------------
    def create_menu_bar(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.load_file)

        save_action = QAction("另存为(&S)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_figure)

        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        file_menu.addActions([open_action, save_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        overlay_action = QAction("叠加地图", self)
        overlay_action.triggered.connect(self.overlay_map)
        view_menu.addAction(overlay_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        qc_action = QAction("质量控制", self)
        qc_action.triggered.connect(self.quality_control)
        edit_menu.addAction(qc_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    # ---------------------- 文件操作 ----------------------
    def load_file(self):
        radar, file = load_radar_via_dialog(self, self.status_bar)
        if radar is None:
            return

        self.radar = radar
        self.radar_file = file

        # 初始化界面
        self.init_main_interface()
        self.el_combo.clear()
        self.var_combo.clear()
        for el in radar.el:
            self.el_combo.addItem(f"{el:.1f}")
        for v in radar.available_product(0):
            self.var_combo.addItem(v)

    def save_figure(self):
        if not self.canvas:
            QMessageBox.warning(self, "提示", "暂无可保存的图像！")
            return
        file, _ = QFileDialog.getSaveFileName(self, "另存为", "", "PNG 图像 (*.png);;JPG 图像 (*.jpg)")
        if file:
            self.fig.savefig(file, dpi=300)
            self.status_bar.showMessage(f"图像已保存至：{file}")

    # ---------------------- 主界面 ----------------------
    def init_main_interface(self):
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 左侧控件
        left_layout = QVBoxLayout()
        group_params = QGroupBox("数据与绘图参数")
        params_layout = QVBoxLayout()

        self.file_path = QLabel(f"当前文件:\n{os.path.basename(self.radar_file)}")

        self.el_label = QLabel("仰角层：")
        self.el_combo = QComboBox()

        self.var_label = QLabel("数据类型：")
        self.var_combo = QComboBox()

        self.range_label = QLabel("探测范围 (km)：")
        self.range_input = QLineEdit("75")

        self.plot_btn = QPushButton("绘制图像")
        self.plot_btn.clicked.connect(self.plot_data)

        params_layout.addWidget(self.file_path)
        params_layout.addWidget(self.el_label)
        params_layout.addWidget(self.el_combo)
        params_layout.addWidget(self.var_label)
        params_layout.addWidget(self.var_combo)
        params_layout.addWidget(self.range_label)
        params_layout.addWidget(self.range_input)
        params_layout.addWidget(self.plot_btn)
        group_params.setLayout(params_layout)

        left_layout.addWidget(group_params)
        left_layout.addStretch()
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # 绘图区
        self.fig = Figure(figsize=(6, 6))
        self.canvas = FigureCanvas(self.fig)

        # 事件绑定
        if self._mouse_cid is None:
            self._mouse_cid = self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        if self._press_cid is None:
            self._press_cid = self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        if self._release_cid is None:
            self._release_cid = self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        if self._motion_cid is None:
            self._motion_cid = self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
        if self._scroll_cid is None:
            self._scroll_cid = self.canvas.mpl_connect("scroll_event", self.on_scroll_mpl)

        # 添加到主布局
        self.main_layout.addWidget(left_widget, 1)
        self.main_layout.addWidget(self.canvas, 3)

    # ---------------------- 绘图 ----------------------
    def plot_data(self):
        if self.radar is None:
            QMessageBox.warning(self, "提示", "请先选择并解析文件！")
            return

        tilt = self.el_combo.currentIndex()
        dtype = self.var_combo.currentText()
        try:
            drange = float(self.range_input.text())
        except ValueError:
            QMessageBox.warning(self, "错误", "探测范围必须为数字！")
            return

        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        result = plot_radar_data(
            self.fig, self.radar, tilt, dtype, drange,
            self.radar_file, self.county_shp, self.map_visible
        )

        if result["success"]:
            self.ax = result["ax"]
            self.map_features = result["features"]
            self.canvas.draw()
            self.status_bar.showMessage("绘图完成")
            # 保存初始视图范围
            self._orig_extent = self.ax.get_extent(crs=ccrs.PlateCarree())
        else:
            QMessageBox.critical(self, "错误", result["error"])

    # ---------------------- 鼠标显示经纬度 ----------------------
    def on_mouse_move(self, event):
        if self.ax is None or event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            self.status_bar.clearMessage()
            return
        try:
            lon, lat = ccrs.PlateCarree().transform_point(event.xdata, event.ydata, self.ax.projection)
            self.status_bar.showMessage(f"Lon: {lon:.3f}°, Lat: {lat:.3f}°")
        except Exception:
            self.status_bar.clearMessage()

    # ---------------------- 地图叠加 ----------------------
    def overlay_map(self):
        if not self.canvas or not self.fig.axes:
            QMessageBox.warning(self, "提示", "请先绘制图像！")
            return

        self.ax = self.fig.axes[0]
        if not self.map_features:
            self.map_features = create_map_features_on_ax(self.ax, self.county_shp)
            self.map_visible = True
            self.status_bar.showMessage("已叠加地图。")
        else:
            for artist in self.map_features:
                artist.set_visible(not self.map_visible)
            self.map_visible = not self.map_visible
            msg = "已叠加地图。" if self.map_visible else "已取消叠加地图。"
            self.status_bar.showMessage(msg)
        self.canvas.draw()

    # ---------------------- 平移 ----------------------
    def on_mouse_press(self, event):
        if self.ax is None or event.inaxes != self.ax:
            return

        if event.button == 1:  # 左键拖曳平移
            try:
                lon, lat = ccrs.PlateCarree().transform_point(event.xdata, event.ydata, self.ax.projection)
                self._is_panning = True
                self._pan_start = (lon, lat)
                self._pan_extent = list(self.ax.get_extent(crs=ccrs.PlateCarree()))
            except Exception:
                self._is_panning = False
                self._pan_start = None

        elif event.button == 3:  # 右键复位
            if hasattr(self, "_orig_extent") and self._orig_extent is not None:
                try:
                    self.ax.set_extent(self._orig_extent, crs=ccrs.PlateCarree())
                    self.canvas.draw_idle()
                    self.status_bar.showMessage("已复位到初始视图")
                except Exception:
                    pass

    def on_mouse_release(self, event):
        if self._is_panning:
            self._is_panning = False
            self._pan_start = None
            self._pan_extent = None

    def on_mouse_drag(self, event):
        if not self._is_panning or self.ax is None or event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        try:
            cur_lon, cur_lat = ccrs.PlateCarree().transform_point(event.xdata, event.ydata, self.ax.projection)
            start_lon, start_lat = self._pan_start
            dlon = start_lon - cur_lon
            dlat = start_lat - cur_lat
            lon_min, lon_max, lat_min, lat_max = self._pan_extent
            new_extent = [lon_min + dlon, lon_max + dlon, lat_min + dlat, lat_max + dlat]
            self.ax.set_extent(new_extent, crs=ccrs.PlateCarree())
            self.canvas.draw_idle()
        except Exception:
            pass

    # ---------------------- 滚轮缩放 ----------------------
    def on_scroll_mpl(self, event):
        if self.ax is None or event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        try:
            center_lon, center_lat = ccrs.PlateCarree().transform_point(event.xdata, event.ydata,
                                                                        self.ax.projection)
            lon_min, lon_max, lat_min, lat_max = self.ax.get_extent(crs=ccrs.PlateCarree())
            base_scale = 1.2
            scale = 1.0 / base_scale if event.button == 'up' else base_scale
            lon_left = center_lon - (center_lon - lon_min) * scale
            lon_right = center_lon + (lon_max - center_lon) * scale
            lat_bottom = center_lat - (center_lat - lat_min) * scale
            lat_top = center_lat + (lat_max - center_lat) * scale
            # 最小跨度
            MIN_LON_SPAN = 0.01
            MIN_LAT_SPAN = 0.01
            if (lon_right - lon_left) < MIN_LON_SPAN:
                lon_left = center_lon - MIN_LON_SPAN / 2
                lon_right = center_lon + MIN_LON_SPAN / 2
            if (lat_top - lat_bottom) < MIN_LAT_SPAN:
                lat_bottom = center_lat - MIN_LAT_SPAN / 2
                lat_top = center_lat + MIN_LAT_SPAN / 2
            # 限制范围
            lon_left = max(-180, lon_left)
            lon_right = min(180, lon_right)
            lat_bottom = max(-90, lat_bottom)
            lat_top = min(90, lat_top)
            self.ax.set_extent([lon_left, lon_right, lat_bottom, lat_top], crs=ccrs.PlateCarree())
            self.canvas.draw_idle()
        except Exception:
            pass

    def quality_control(self):
        QMessageBox.information(self, "提示", "质量控制功能尚未实现。")

    def show_about(self):
        QMessageBox.about(self, "关于", "X波段雷达基数据可视化软件\n版本：v1.0\n作者：lihb")

