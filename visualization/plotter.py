import os
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from cartopy.feature import ShapelyFeature
from cinrad.visualize.utils import cmap_plot, norm_plot
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size': 14})


def create_map_features_on_ax(ax, shp_path=None):
    """在 ax 上添加地图要素"""
    features = []
    base_feats = [
        cfeature.COASTLINE.with_scale('50m'),
        cfeature.BORDERS.with_scale('50m'),
        cfeature.LAKES.with_scale('50m'),
        cfeature.RIVERS.with_scale('50m')
    ]
    for feat in base_feats:
        features.append(ax.add_feature(feat, linewidth=0.5))

    if shp_path and os.path.exists(shp_path):
        try:
            reader = shpreader.Reader(shp_path)
            county_feature = ShapelyFeature(
                reader.geometries(), ccrs.PlateCarree(),
                edgecolor='black', facecolor='none', linewidth=1.3
            )
            features.append(ax.add_feature(county_feature))
        except Exception:
            pass
    return features

def plot_radar_data(fig, radar, tilt, product, drange, radar_file, shp_path,
                    map_visible=False, data_qc=None):
    """
    绘制雷达数据并返回结果
    :param fig: matplotlib Figure 对象
    :param radar: StandardData 对象
    :param tilt: 仰角索引
    :param product: 变量名称
    :param drange: 探测范围（km）
    :param radar_file: 雷达文件路径（用于标题显示）
    :param shp_path: shapefile
    :param map_visible: 是否显示地图要素
    :param data_qc: numpy 数组（质控后的数据，可为 None）
    :return: dict 包含 success、ax、features 或 error
    """
    try:
        ds = radar.get_data(tilt=tilt, drange=drange, dtype=product)
        lon, lat = ds["longitude"], ds["latitude"]

        # 判断是否使用质控后的数据
        if data_qc is not None:
            print("使用质控后的数据绘图。")
            data = data_qc
        else:
            data = ds[product].values

        # 清空旧图像
        fig.clear()

        # 创建新的 Axes（地图投影）
        ax = fig.add_subplot(
            111,
            projection=ccrs.AzimuthalEquidistant(
                central_longitude=106.59101,
                central_latitude=28.8131
            )
        )
        # 动态获取 colormap 与 norm
        product_upper = product.upper()
        cmap = cmap_plot.get(product_upper, plt.get_cmap("turbo"))
        norm = norm_plot.get(product_upper, None)

        # 绘制雷达数据
        pcm = ax.pcolormesh(
            lon, lat, data,
            shading="auto",
            cmap=cmap,
            norm=norm,
            transform=ccrs.PlateCarree()
        )

        # 设置经纬度范围
        ax.set_extent(
            [float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())],
            crs=ccrs.PlateCarree()
        )

        # 经纬网格
        gl = ax.gridlines(draw_labels=True, linewidth=0.0, color='gray', alpha=0.5)
        gl.top_labels = gl.right_labels = False

        # 标题和颜色条
        filename = os.path.basename(radar_file)
        ax.set_title(f"{filename}\n{product} @ {ds.attrs.get('elevation', 0):.1f}° ({drange} km)")
        fig.colorbar(pcm, ax=ax, label=product)

        # 叠加地图要素（可选）
        features = []
        if map_visible:
            features = create_map_features_on_ax(ax, shp_path)

        return {"success": True, "ax": ax, "features": features}

    except Exception as e:
        return {"success": False, "error": str(e)}

