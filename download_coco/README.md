# COCO 数据集下载工具

一个简单易用的 COCO 2017 数据集下载工具，支持图形界面、断点续传和多线程下载。

## 功能特点

- 图形化界面，操作简单直观
- 支持自定义下载位置
- 支持断点续传
- 多线程下载，提高下载速度
- 自动验证文件完整性
- 支持清理缓存
- 显示详细的下载进度
- 跨平台支持（Windows/macOS/Linux）

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/你的用户名/coco-downloader.git
cd coco-downloader
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行程序：
```bash
python download_coco.py
```

2. 在图形界面中：
   - 选择下载位置
   - 点击"开始下载"开始下载
   - 如需重新开始，点击"清理缓存"

## 数据集说明

COCO 2017 数据集包含：
- 训练集图像（约18GB）
- 验证集图像（约815MB）
- 标注文件（约241MB）

## 注意事项

- 确保有足够的磁盘空间
- 建议使用稳定的网络连接
- 下载过程中可以随时中断，支持断点续传
- 下载完成后会自动解压并删除压缩文件

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 作者

你的名字 