import os
from cinrad.io import read_auto, StandardData
from PyQt5.QtWidgets import QFileDialog, QMessageBox

def load_radar_file(file_path):
    """
    读取雷达文件并返回 StandardData 对象。
    :param file_path: 文件路径
    :return: StandardData 对象 或 None
    """
    try:
        radar = read_auto(file_path)
        if not isinstance(radar, StandardData):
            raise TypeError(f"文件 {file_path} 不是标准雷达数据")
        return radar
    except Exception:
        return None

def load_radar_via_dialog(parent, status_bar=None):
    """
    弹出文件选择对话框并解析雷达文件。
    :param parent: 父窗口（QWidget），用于 QMessageBox
    :param status_bar: QStatusBar，可选，用于显示状态信息
    :return: radar 对象 或 None, 文件路径
    """
    file, _ = QFileDialog.getOpenFileName(
        parent, "选择雷达数据文件", "", "雷达文件 (*.bin *.bz2 *.gz);;所有文件 (*)"
    )
    if not file:
        return None, None

    if status_bar:
        status_bar.showMessage("正在解析文件...")

    radar = load_radar_file(file)
    if radar is None:
        QMessageBox.critical(parent, "错误", "非标准格式雷达数据")
        if status_bar:
            status_bar.showMessage("文件解析失败")
        return None, None

    QMessageBox.information(parent, "消息", "文件解析成功！")
    if status_bar:
        status_bar.showMessage(f"已加载文件：{os.path.basename(file)}")

    return radar, file
