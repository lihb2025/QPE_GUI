import numpy as np
from scipy.ndimage import gaussian_filter


def ground_clutter_filter(self):
    """地物杂波抑制"""
    print("执行地物杂波抑制...")
    tilt = self.el_combo.currentIndex()
    product = self.var_combo.currentText().upper()
    drange = float(self.range_input.text())

    # 读取当前层的数据
    ds_ref = self.radar.get_data(tilt=tilt, drange=drange, dtype=product)
    ds_vel = self.radar.get_data(tilt=tilt, drange=drange, dtype="VEL")
    ds_sw  = self.radar.get_data(tilt=tilt, drange=drange, dtype="SW")

    # 提取 numpy 数组（xarray.DataArray → np.ndarray）
    ref = ds_ref[product].values
    vel = ds_vel["VEL"].values
    sw  = ds_sw["SW"].values

    # 屏蔽速度接近0且谱宽小的杂波
    clutter_mask = (np.abs(vel) < 1) & (sw < 1)
    ref[clutter_mask] = np.nan

    # 平滑处理
    ref_filtered = gaussian_filter(ref, sigma=1)
    self.data_qc = ref_filtered
    print("地物杂波抑制完成。")

def attenuation_correction(self):
    """衰减订正并写回 radar_qc"""
    print("执行衰减订正...")
    tilt = self.el_combo.currentIndex()
    product = self.var_combo.currentText().upper()

    # 读取数据
    ds_ref = self.radar.get_data(tilt=tilt, drange=75, dtype=product)
    ref = ds_ref[product].values

    nrange = ref.shape[1]
    correction = np.linspace(1.0, 5.0, nrange)
    R = 10 ** (ref / 10)
    R_corrected = R * correction[None, :]
    ref_corrected = 10 * np.log10(R_corrected)
    ref_corrected = np.clip(ref_corrected, -10, 80)
    self.data_qc = ref_corrected
    print("衰减订正完成。")