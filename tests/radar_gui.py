import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QComboBox, QLineEdit, QAction, QGroupBox, QStatusBar
)
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from cinrad.io import read_auto, StandardData
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from cartopy.feature import ShapelyFeature

class RadarViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X波段雷达基数据可视化软件")
        self.setWindowIcon(QIcon(r"C:\Users\lihb\PycharmProjects\QPE_GUI\radar.ico"))
        self.resize(1100, 650)

        # 状态栏（主状态与右侧经纬度显示）
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        # self.status_bar.addPermanentWidget(self.coord_label)

        # 初始化：主界面为空
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # 雷达对象占位
        self.radar = None
        self.radar_file = None  #  新增：保存文件路径

        # 当前 ax（保持引用，避免混淆）
        self.ax = None

        # 地图要素状态与缓存（初始化）
        self.map_features = []     # 存当前 ax 上的 feature artists
        self.map_visible = False   # 是否处于“可见”状态

        # shapefile 路径（按需修改）
        self.county_shp = r"D:\lihb\work\cqqx\cn\中华人民共和国.shp"

        # 菜单栏
        self.create_menu_bar()

        # 预定义绘图组件
        self.left_panel = None
        self.canvas = None

    # ---------------------- 菜单栏设计 ----------------------
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

        cmap_action = QAction("更换颜色映射", self)
        cmap_action.triggered.connect(self.change_colormap)
        view_menu.addAction(cmap_action)

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

    # ---------------------- 文件功能 ----------------------
    def load_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "选择雷达数据文件", "", "雷达文件 (*.bin *.bz2 *.gz);;所有文件 (*)"
        )
        if not file:
            return

        self.status_bar.showMessage("正在解析文件...")

        try:
            radar = read_auto(file)
            if not isinstance(radar, StandardData):
                raise TypeError
            self.radar = radar
            self.radar_file = file  #  保存文件路径
        except Exception:
            QMessageBox.critical(self, "错误", "非标准格式雷达数据")
            self.status_bar.showMessage("文件解析失败")
            self.radar = None
            return

        QMessageBox.information(self, "消息", "文件解析成功！")
        self.status_bar.showMessage(f"已加载文件：{os.path.basename(file)}")

        # 加载成功后初始化主界面
        self.init_main_interface()

        # 更新仰角与变量
        self.el_combo.clear()
        self.var_combo.clear()
        for el in radar.el:
            self.el_combo.addItem(f"{el:.1f}")
        products = radar.available_product(0)
        for v in products:
            self.var_combo.addItem(v)

    def save_figure(self):
        if not self.canvas:
            QMessageBox.warning(self, "提示", "暂无可保存的图像！")
            return
        file, _ = QFileDialog.getSaveFileName(self, "另存为", "", "PNG 图像 (*.png);;JPG 图像 (*.jpg)")
        if file:
            self.fig.savefig(file, dpi=300)
            self.status_bar.showMessage(f"图像已保存至：{file}")

    # ---------------------- 初始化主界面 ----------------------
    def init_main_interface(self):
        """在成功打开文件后，创建左侧控件和右侧绘图区"""
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # 左侧控件
        left_layout = QVBoxLayout()
        group_params = QGroupBox("数据与绘图参数")
        params_layout = QVBoxLayout()

        #  改为使用 self.radar_file
        self.file_path = QLabel(f"当前文件:\n"
                                f"{os.path.basename(self.radar_file)}")

        self.el_label = QLabel("仰角层：")
        self.el_combo = QComboBox()

        self.var_label = QLabel("变量：")
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

        # 绘图区（只创建一次）
        self.fig = Figure(figsize=(6, 6))
        self.canvas = FigureCanvas(self.fig)

        # 关键：在创建 canvas 后立即绑定鼠标移动事件（事件必须绑定到 self.canvas）
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)

        # 添加到主布局
        self.main_layout.addWidget(left_widget, 1)
        self.main_layout.addWidget(self.canvas, 3)

    # ---------------------- 辅助：在给定 ax 上创建地图要素并返回 artists 列表 ----------------------
    def _create_map_features_on_ax(self, ax):
        """在 ax 上添加地图要素，返回一个 artist 列表（便于后续 set_visible）"""
        artists = []
        base_feats = [
            cfeature.COASTLINE.with_scale('50m'),
            cfeature.BORDERS.with_scale('50m'),
            cfeature.LAKES.with_scale('50m'),
            cfeature.RIVERS.with_scale('50m')
        ]
        for feat in base_feats:
            a = ax.add_feature(feat, linewidth=0.5)
            artists.append(a)

        # 加载区县 shapefile（若存在）
        if os.path.exists(self.county_shp):
            try:
                reader = shpreader.Reader(self.county_shp)
                county_feature = ShapelyFeature(
                    reader.geometries(), ccrs.PlateCarree(),
                    edgecolor='black', facecolor='none', linewidth=0.3
                )
                a = ax.add_feature(county_feature)
                artists.append(a)
            except Exception:
                # 不阻塞主逻辑，记录状态
                pass
        return artists

    # ---------------------- 绘图功能 ----------------------
    def plot_data(self):
        if self.radar is None:
            QMessageBox.warning(self, "提示", "请先选择并解析文件！")
            return

        tilt = self.el_combo.currentIndex()
        product = self.var_combo.currentText()
        try:
            drange = float(self.range_input.text())
        except ValueError:
            QMessageBox.warning(self, "错误", "探测范围必须为数字！")
            return

        try:
            ds = self.radar.get_data(tilt=tilt, drange=drange, dtype=product)
            data = ds[product]
        except Exception as e:
            QMessageBox.critical(self, "错误", f"数据读取失败: {e}")
            return

        # 重新清空 figure 并创建新的 GeoAxes（但我们会维护 self.ax 引用）
        self.fig.clear()
        self.ax = self.fig.add_subplot(
            111,
            projection=ccrs.AzimuthalEquidistant(central_longitude=106.59101, central_latitude=28.8131)
        )

        # 只有在 map_features 非空且这些 artist 很可能绑定旧 axes 时，清空它们的引用
        # 如果之前地图处于可见（map_visible True），将会在新 ax 上重建它们下面逻辑会处理
        if self.map_features:
            self.map_features = []

        lon, lat = ds["longitude"], ds["latitude"]
        pcm = self.ax.pcolormesh(lon, lat, data, shading="auto",
                                 cmap="turbo", transform=ccrs.PlateCarree())

        # 添加经纬网格与范围
        try:
            self.ax.set_extent([float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())], crs=ccrs.PlateCarree())
        except Exception:
            pass
        gl = self.ax.gridlines(draw_labels=True, linewidth=0.0, color='gray', alpha=0.5)
        # 避免每次都覆盖 label 样式（可选）
        gl.top_labels = False
        gl.right_labels = False

        filename = os.path.basename(self.radar_file)  # 仅取文件名部分
        self.ax.set_title(f"{filename}\n{product} @ {ds.attrs.get('elevation', 0):.1f}° ({drange} km)")
        self.fig.colorbar(pcm, ax=self.ax, label=product)

        # 关键：如果之前地图处于“可见”状态，则在新 ax 上重建地图要素并保持可见
        if self.map_visible:
            # 清理旧的 references（它们绑定旧 ax），然后在新 ax 上创建并保存
            self.map_features = self._create_map_features_on_ax(self.ax)
            # 这些新创建的 artists 默认是可见的，map_visible 保持 True

        # 刷新画布
        self.canvas.draw()
        self.status_bar.showMessage("绘图完成")

    # ---------------------- 鼠标移动回调：显示经纬度 ----------------------
    def on_mouse_move(self, event):
        """鼠标移动时在状态栏显示经纬度"""
        if self.ax is None:
            return

        # 如果鼠标不在绘图区域上，则清空状态栏
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            self.statusBar().clearMessage()
            return

        try:
            lon, lat = ccrs.PlateCarree().transform_point(
                event.xdata, event.ydata, self.ax.projection
            )
            self.statusBar().showMessage(f"Lon: {lon:.3f}°, Lat: {lat:.3f}°")
        except Exception:
            self.statusBar().clearMessage()

    # ---------------------- 叠加地图 ----------------------
    def overlay_map(self):
        # 先确保有 ax（即已经绘图）
        if not self.canvas or not self.fig.axes:
            QMessageBox.warning(self, "提示", "请先绘制图像！")
            return

        # 保证 self.ax 指向当前 axes
        self.ax = self.fig.axes[0]

        # 如果还没有任何 map_features（第一次点击或已被 plot_data 清空），则创建并显示
        if not self.map_features:
            self.map_features = self._create_map_features_on_ax(self.ax)
            self.map_visible = True
            self.status_bar.showMessage("已叠加地图。")
            self.canvas.draw()
            return

        # 如果已经有要素，根据当前可见状态切换显示/隐藏
        if self.map_visible:
            # 隐藏这些要素
            for artist in self.map_features:
                try:
                    artist.set_visible(False)
                except Exception:
                    pass
            self.map_visible = False
            self.status_bar.showMessage("已取消叠加地图。")
        else:
            # 显示这些要素（它们已存在于当前 ax 或者刚在 plot_data 时被重建）
            for artist in self.map_features:
                try:
                    artist.set_visible(True)
                except Exception:
                    pass
            self.map_visible = True
            self.status_bar.showMessage("已重新叠加地图。")

        self.canvas.draw()

    # ---------------------- 菜单动作 ----------------------
    def change_colormap(self):
        QMessageBox.information(self, "提示", "未来可在此处实现颜色映射切换功能。")

    def quality_control(self):
        QMessageBox.information(self, "提示", "质量控制功能尚未实现，可后续扩展。")

    def show_about(self):
        QMessageBox.about(
            self,
            "关于",
            "X波段雷达基数据可视化软件\n\n版本：v1.0\n作者：lihb\n说明：用于读取与可视化标准格式雷达数据。",
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = RadarViewer()
    viewer.show()
    sys.exit(app.exec_())
