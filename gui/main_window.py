import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QRadioButton,
    QFileDialog, QMessageBox, QComboBox, QLineEdit, QAction, QGroupBox, QStatusBar
)
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from visualization.plotter import plot_radar_data, create_map_features_on_ax
import cartopy.crs as ccrs
from iodata.read_radar import load_radar_via_dialog, load_radar_file
from qc.qc_methods import ground_clutter_filter, attenuation_correction


class RadarViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X波段天气雷达数据处理与可视化软件")
        self.setWindowIcon(QIcon(r"C:\Users\lihb\PycharmProjects\QPE_GUI\resources\radar.ico"))
        self.county_shp = r"C:\Users\lihb\PycharmProjects\QPE_GUI\resources\ZA702_BOUL.shp"
        self.resize(1100, 650)

        # 主界面布局
        self.create_menu_bar()
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.central_widget.setLayout(self.main_layout)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 数据文件
        self.radar = None
        self.radar_file = None
        self.folder_path = None
        self.file_list = []
        self.current_index = -1

        # 交互状态
        self._is_panning = False
        self._pan_start = None
        self._pan_extent = None
        self._mouse_cid = None
        self._press_cid = None
        self._release_cid = None
        self._motion_cid = None
        self._scroll_cid = None

        # 绘图与当前状态
        self.ax = None
        self.map_features = []
        self.map_visible = False
        self.left_panel = None
        self.canvas = None
        self.current_el = None
        self.current_product = None
        self.data_qc = None

    # ---------------------- 菜单栏 ----------------------
    def create_menu_bar(self):
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")
        open_action = QAction("打开(&O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.load_file)

        open_folder_action = QAction("打开文件夹(&D)", self)
        open_folder_action.setShortcut("Ctrl+D")
        open_folder_action.triggered.connect(self.load_folder)

        save_action = QAction("另存为(&S)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_figure)

        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        file_menu.addActions([open_action, open_folder_action, save_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        overlay_action = QAction("叠加地图", self)
        overlay_action.triggered.connect(self.overlay_map)
        view_menu.addAction(overlay_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")
        data_process_menu = edit_menu.addMenu("数据处理")
        # --- 质量控制 ---
        qc_menu = data_process_menu.addMenu("质量控制")
        qc_action = QAction("地物杂波抑制", self)
        qc_action.triggered.connect(lambda: self.apply_qc_from_menu("clutter"))
        qc_menu.addAction(qc_action)

        # --- 偏差订正 ---
        correction_menu = data_process_menu.addMenu("偏差订正")
        attenuation_action = QAction("衰减订正", self)
        attenuation_action.triggered.connect(lambda: self.apply_qc_from_menu("attenuation"))
        correction_menu.addAction(attenuation_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")
        about_action = QAction("关于...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    # ---------------------- 打开文件夹 ----------------------
    def load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择雷达数据文件夹")
        if not folder:
            return
        self.folder_path = folder
        files = [f for f in os.listdir(folder) if f.lower().endswith(".bz2")]
        if not files:
            QMessageBox.warning(self, "提示", "该文件夹中未找到 .bz2 文件！")
            return

        # 排序并保存文件列表
        files.sort()
        self.file_list = [os.path.join(folder, f) for f in files]
        self.current_index = 0

        # 加载第一个文件
        self.load_radar_file_by_index(0)

    def load_radar_file_by_index(self, idx):
        if not self.file_list or idx < 0 or idx >= len(self.file_list):
            QMessageBox.warning(self, "提示", "没有更多文件！")
            return

        file = self.file_list[idx]
        radar = load_radar_file(file)
        if radar is None:
            QMessageBox.critical(self, "错误", f"文件解析失败：{os.path.basename(file)}")
            return

        self.radar = radar
        self.radar_file = file
        self.current_index = idx

        if not hasattr(self, "el_combo"):
            self.init_main_interface()
        if not hasattr(self, "var_combo"):
            self.init_main_interface()

        # 更新文件显示
        if hasattr(self, "file_path"):
            self.file_path.setText(f"当前文件:\n{os.path.basename(self.radar_file)}")
        # 更新仰角与产品下拉项（保留当前选择索引的策略）
        prev_el_idx = self.el_combo.currentIndex() if self.el_combo.count() > 0 else None
        prev_product = self.var_combo.currentText() if self.var_combo.count() > 0 else None

        self.el_combo.clear()
        self.var_combo.clear()
        for el in radar.el:
            self.el_combo.addItem(f"{el:.1f}")
        for v in radar.available_product(0):
            self.var_combo.addItem(v)

        # 恢复先前的索引
        if prev_el_idx is not None and 0 <= prev_el_idx < self.el_combo.count():
            self.el_combo.setCurrentIndex(prev_el_idx)
        if prev_product and prev_product in [self.var_combo.itemText(i) for i in range(self.var_combo.count())]:
            self.var_combo.setCurrentText(prev_product)

        self.status_bar.showMessage(f"已加载文件：{os.path.basename(file)}")

    # ---------------------- 打开单个文件 ----------------------
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

    # ---------------------- 翻页功能 ----------------------
    def load_previous_file(self):
        if not self.file_list:
            QMessageBox.warning(self, "提示", "请先打开文件夹！")
            return
        if self.current_index <= 0:
            QMessageBox.information(self, "提示", "已是第一个文件。")
            return
        # 记住当前选择
        self.current_el = self.el_combo.currentIndex()
        self.current_product = self.var_combo.currentText()

        self.load_radar_file_by_index(self.current_index - 1)
        self.restore_previous_settings()

    def load_next_file(self):
        if not self.file_list:
            QMessageBox.warning(self, "提示", "请先打开文件夹！")
            return
        if self.current_index >= len(self.file_list) - 1:
            QMessageBox.information(self, "提示", "已是最后一个文件。")
            return
        self.current_el = self.el_combo.currentIndex()
        self.current_product = self.var_combo.currentText()

        self.load_radar_file_by_index(self.current_index + 1)
        self.restore_previous_settings()

    def restore_previous_settings(self):
        if self.current_el is not None:
            self.el_combo.setCurrentIndex(self.current_el)
        if self.current_product is not None:
            self.var_combo.setCurrentText(self.current_product)
        self.plot_data()

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
        group_params = QGroupBox("数据绘图")
        params_layout = QVBoxLayout()

        # 文件路径标签等控件（如果已经存在，就复用，否则新建）
        if not hasattr(self, "file_path") or self.file_path is None:
            self.file_path = QLabel(f"当前文件:\n{os.path.basename(self.radar_file) if self.radar_file else ''}")
        else:
            # 更新显示文本
            self.file_path.setText(f"当前文件:\n{os.path.basename(self.radar_file) if self.radar_file else ''}")

        if not hasattr(self, "el_combo") or self.el_combo is None:
            self.el_label = QLabel("仰角层：")
            self.el_combo = QComboBox()
        else:
            self.el_label = getattr(self, "el_label", QLabel("仰角层："))

        if not hasattr(self, "var_combo") or self.var_combo is None:
            self.var_label = QLabel("数据类型：")
            self.var_combo = QComboBox()
        else:
            self.var_label = getattr(self, "var_label", QLabel("数据类型："))

        if not hasattr(self, "range_input") or self.range_input is None:
            self.range_label = QLabel("探测范围 (km)：")
            self.range_input = QLineEdit("75")
        else:
            self.range_label = getattr(self, "range_label", QLabel("探测范围 (km)："))

        if not hasattr(self, "plot_btn") or self.plot_btn is None:
            self.plot_btn = QPushButton("绘制图像")
            self.plot_btn.clicked.connect(self.plot_data)

        # 前后翻页按钮
        if not hasattr(self, "prev_btn") or self.prev_btn is None:
            btn_layout = QHBoxLayout()
            self.prev_btn = QPushButton("前一时次")
            self.prev_btn.clicked.connect(self.load_previous_file)
            self.next_btn = QPushButton("后一时次")
            self.next_btn.clicked.connect(self.load_next_file)
            btn_layout.addWidget(self.prev_btn)
            btn_layout.addWidget(self.next_btn)
        else:
            btn_layout = QHBoxLayout()
            btn_layout.addWidget(self.prev_btn)
            btn_layout.addWidget(self.next_btn)

        params_layout.addWidget(self.file_path)
        params_layout.addWidget(self.el_label)
        params_layout.addWidget(self.el_combo)
        params_layout.addWidget(self.var_label)
        params_layout.addWidget(self.var_combo)
        params_layout.addWidget(self.range_label)
        params_layout.addWidget(self.range_input)
        params_layout.addWidget(self.plot_btn)
        params_layout.addLayout(btn_layout)
        group_params.setLayout(params_layout)

        left_layout.addWidget(group_params)
        left_layout.addStretch()
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        # 数据处理部分
        group_qc = QGroupBox("数据处理")
        qc_layout = QVBoxLayout()

        self.qc_clutter = QRadioButton("地物杂波抑制")
        self.qc_attenuation = QRadioButton("衰减订正")
        self.btn_apply_qc = QPushButton("应用")

        # 添加到布局
        qc_layout.addWidget(self.qc_clutter)
        qc_layout.addWidget(self.qc_attenuation)
        qc_layout.addWidget(self.btn_apply_qc)

        group_qc.setLayout(qc_layout)
        left_layout.addWidget(group_qc)
        # 保持左侧控件整体靠上
        left_layout.addStretch()

        # 绘图区：只在第一次创建 fig/canvas；如果已存在则复用并确保加入布局
        if not hasattr(self, "fig") or self.fig is None:
            self.fig = Figure(figsize=(6, 6))
        if not hasattr(self, "canvas") or self.canvas is None:
            self.canvas = FigureCanvas(self.fig)
            # 只在创建 canvas 时绑定事件（确保只绑定一次）
            if getattr(self, "_mouse_cid", None) is None:
                self._mouse_cid = self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
            if getattr(self, "_press_cid", None) is None:
                self._press_cid = self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
            if getattr(self, "_release_cid", None) is None:
                self._release_cid = self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
            if getattr(self, "_motion_cid", None) is None:
                self._motion_cid = self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
            if getattr(self, "_scroll_cid", None) is None:
                self._scroll_cid = self.canvas.mpl_connect("scroll_event", self.on_scroll_mpl)
        else:
            try:
                # 有时候 canvas 绑定了旧的 fig，尝试把 canvas 的 figure 指向当前 fig
                self.canvas.figure = self.fig
            except Exception:
                pass

        self.btn_apply_qc.clicked.connect(self.apply_qc)

        # 添加到主布局
        self.main_layout.addWidget(left_widget, 1)
        self.main_layout.addWidget(self.canvas, 3)
        # 如果之前已有 ax，可以保持，不强制 new ax
        if not hasattr(self, "ax") or self.ax is None:
            self.ax = self.fig.add_subplot(111)

    # ---------------------- 绘图 ----------------------
    def plot_data(self):
        if self.radar is None:
            QMessageBox.warning(self, "提示", "请先选择并解析文件！")
            return

        # 保存用户当前选择
        self.current_el = self.el_combo.currentIndex()
        self.current_product = self.var_combo.currentText()
        tilt = self.el_combo.currentIndex()
        product = self.var_combo.currentText()
        try:
            drange = float(self.range_input.text())
        except ValueError:
            QMessageBox.warning(self, "错误", "探测范围必须为数字！")
            return

        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        result = plot_radar_data(
            self.fig, self.radar, tilt, product, drange, self.radar_file, self.county_shp,
            self.map_visible, self.data_qc
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

    # ---------------------- 鼠标事件 ----------------------
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

    def apply_qc(self):
        if not (self.qc_clutter.isChecked() or self.qc_attenuation.isChecked()):
            QMessageBox.information(self, "提示", "请至少勾选一种处理方法！")
            return

        if self.radar is None:
            QMessageBox.warning(self, "警告", "请先加载雷达数据！")
            return

        product = self.var_combo.currentText().upper()
        if product not in ["REF", "ZDR", "PHI", "KDP"]:
            QMessageBox.information(self, "提示", "算法仅适用于REF、ZDR、PHI、KDP！")
            return

        # 按勾选调用数据处理算法
        applied_methods = []
        if self.qc_clutter.isChecked():
            ground_clutter_filter(self)
            applied_methods.append("地物杂波抑制")

        elif self.qc_attenuation.isChecked():
            attenuation_correction(self)
            applied_methods.append("衰减订正")

        if not applied_methods:
            QMessageBox.information(self, "提示", "请先选择一种质控方法！")
            return False

        # 绘图
        self.plot_data()  # 内部逻辑可优先使用 self.qc_data 绘图
        # 清空旧的质控数据
        self.data_qc = None
        self.status_bar.showMessage("已应用数据处理：" + "、".join(applied_methods))

    def apply_qc_from_menu(self, method):
        """菜单点击时调用，统一到 apply_qc()"""
        # 先清空所有勾选
        self.qc_clutter.setChecked(False)
        self.qc_attenuation.setChecked(False)

        # 根据菜单选择勾选对应的选项
        if method == "clutter":
            self.qc_clutter.setChecked(True)
        elif method == "attenuation":
            self.qc_attenuation.setChecked(True)

        # 调用统一的数据处理逻辑
        self.apply_qc()

    def show_about(self):
        QMessageBox.about(self, "关于", "X波段天气雷达数据处理与可视化软件\n版本：v1.0\n作者：lihb")