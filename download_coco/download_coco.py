"""
COCO 2017数据集下载脚本

这个脚本用于下载COCO 2017数据集，包括：
1. 训练集图像（约18GB）
2. 验证集图像（约815MB）
3. 标注文件（约241MB）

特点：
- 支持多线程下载，提高下载速度
- 支持断点续传
- 文件完整性验证（大小和MD5校验）
- 自动解压和清理
"""

from pycocotools.coco import COCO
import requests
import zipfile
import os
import numpy as np
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import concurrent.futures
import math
import threading
import tempfile
import shutil
import hashlib
import json
import urllib.request
import argparse
import tkinter as tk
from tkinter import ttk
import queue
import time
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog

def get_file_size(url, session):
    """
    获取远程文件的大小
    
    参数:
        url: 文件URL
        session: requests会话对象
    
    返回:
        文件大小（字节）
    """
    response = session.head(url)
    return int(response.headers.get('content-length', 0))

def calculate_file_md5_chunk(args):
    """
    计算文件块的MD5值
    
    参数:
        args: 元组 (filename, start, end)
            - filename: 文件路径
            - start: 起始字节位置
            - end: 结束字节位置
    
    返回:
        文件块的MD5值（十六进制字符串）
    """
    filename, start, end = args
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        f.seek(start)
        remaining = end - start
        while remaining > 0:
            chunk_size = min(remaining, 1024*1024)  # 1MB chunks
            data = f.read(chunk_size)
            if not data:
                break
            hash_md5.update(data)
            remaining -= len(data)
    return hash_md5.hexdigest()

def get_file_md5(filename, num_threads=4):
    """
    使用多线程计算文件的MD5值
    
    参数:
        filename: 文件路径
        num_threads: 线程数，默认4
    
    返回:
        文件的MD5值（十六进制字符串）
    """
    file_size = os.path.getsize(filename)
    chunk_size = file_size // num_threads
    
    # 创建任务
    tasks = []
    for i in range(num_threads):
        start = i * chunk_size
        end = start + chunk_size - 1 if i < num_threads - 1 else file_size - 1
        tasks.append((filename, start, end))
    
    # 使用线程池计算MD5
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(calculate_file_md5_chunk, task) for task in tasks]
        chunk_md5s = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    # 合并所有块的MD5
    final_md5 = hashlib.md5()
    for chunk_md5 in chunk_md5s:
        final_md5.update(bytes.fromhex(chunk_md5))
    
    return final_md5.hexdigest()

def verify_file_integrity(filename, expected_size=None, expected_md5=None):
    """
    验证文件的完整性
    
    参数:
        filename: 文件路径
        expected_size: 期望的文件大小（字节）
        expected_md5: 期望的MD5值
    
    返回:
        (是否完整, 消息)
    """
    if not os.path.exists(filename):
        return False, "文件不存在"
    
    # 检查文件大小
    actual_size = os.path.getsize(filename)
    if expected_size and actual_size != expected_size:
        return False, f"文件大小不匹配: 期望 {expected_size/1024/1024:.2f}MB, 实际 {actual_size/1024/1024:.2f}MB"
    
    # 检查MD5
    if expected_md5:
        print(f'   正在计算文件MD5值...')
        actual_md5 = get_file_md5(filename)
        if actual_md5 != expected_md5:
            return False, f"MD5校验和不匹配: 期望 {expected_md5}, 实际 {actual_md5}"
    
    return True, "文件完整"

def get_coco_file_info():
    """
    获取COCO数据集文件信息
    
    返回:
        包含文件大小和MD5值的字典
    """
    return {
        'train2017.zip': {
            'size': 18000000000,  # 约18GB
            'md5': 'cced6f7f71b7629d05e9705b32467183'  # COCO 2017训练集的MD5值
        },
        'val2017.zip': {
            'size': 815000000,  # 约815MB
            'md5': '442b8da7639aecaf257c1dceb8ba8c80'  # COCO 2017验证集的MD5值
        },
        'annotations_trainval2017.zip': {
            'size': 241000000,  # 约241MB
            'md5': '113a836d90195ee1f884e704da6304df'  # COCO 2017标注文件的MD5值
        }
    }

def download_chunk(args):
    """
    下载文件块
    
    参数:
        args: 包含下载参数的元组
            - url: 文件URL
            - start: 起始字节位置
            - end: 结束字节位置
            - temp_dir: 临时目录
            - filename: 文件名
            - session: requests会话
            - chunk_id: 块ID
            - total_chunks: 总块数
            - total_size: 总文件大小
    
    返回:
        临时文件路径
    """
    url, start, end, temp_dir, filename, session, chunk_id, total_chunks, total_size = args
    temp_file = os.path.join(temp_dir, f"{os.path.basename(filename)}.part{chunk_id}")
    
    # 检查是否存在部分下载的文件
    downloaded_size = 0
    if os.path.exists(temp_file):
        downloaded_size = os.path.getsize(temp_file)
        if downloaded_size > 0:
            start += downloaded_size
    
    headers = {'Range': f'bytes={start}-{end}'}
    response = session.get(url, headers=headers, stream=True)
    chunk_size = end - start + 1
    
    with open(temp_file, 'ab' if downloaded_size > 0 else 'wb') as f:
        for chunk in response.iter_content(chunk_size=8*1024*1024):
            if chunk:
                f.write(chunk)
                downloaded_size += len(chunk)
                progress = (downloaded_size / chunk_size) * 100
                gui.queue.put({
                    'type': 'progress',
                    'chunk_id': chunk_id,
                    'progress': progress
                })
    
    return temp_file

def merge_chunks(filename, chunk_files, temp_dir):
    """
    合并文件块
    
    参数:
        filename: 最终文件名
        chunk_files: 文件块列表
        temp_dir: 临时目录
    """
    buffer_size = 32 * 1024 * 1024  # 32MB buffer
    total_size = sum(os.path.getsize(f) for f in chunk_files)
    
    # 使用固定宽度的进度条
    with tqdm(total=total_size, unit='iB', unit_scale=True, desc='合并文件', ncols=80) as pbar:
        with open(filename, 'wb') as outfile:
            for chunk_file in chunk_files:
                with open(chunk_file, 'rb') as infile:
                    while True:
                        data = infile.read(buffer_size)
                        if not data:
                            break
                        outfile.write(data)
                        pbar.update(len(data))
                os.remove(chunk_file)
    
    # 清理临时目录
    shutil.rmtree(temp_dir)

def create_session():
    """
    创建requests会话
    
    返回:
        配置好的requests会话对象
    """
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def download_file(url, filename):
    """
    下载文件
    
    参数:
        url: 文件URL
        filename: 保存的文件名
    """
    # 检查文件是否已存在
    if os.path.exists(filename):
        print(f'   文件 {filename} 已存在，正在验证完整性...')
        file_info = get_coco_file_info().get(os.path.basename(filename))
        if file_info:
            is_valid, message = verify_file_integrity(filename, file_info['size'], file_info['md5'])
            if is_valid:
                print(f'   ✓ 文件完整性验证通过')
                return
            else:
                print(f'   ✗ {message}')
                print(f'   文件可能损坏，将重新下载')
                os.remove(filename)
        else:
            print(f'   ⚠ 无法验证文件完整性，将重新下载')
            os.remove(filename)

    # 创建会话
    session = create_session()
    
    try:
        # 获取文件大小
        file_size = get_file_size(url, session)
        
        # 根据M3芯片的核心数和SSD特性设置线程数
        num_threads = 4  # 减少线程数，避免SSD I/O瓶颈
        
        # 计算每个块的大小，确保最后一个块不会太小
        base_chunk_size = file_size // num_threads
        remainder = file_size % num_threads
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        
        # 创建下载任务
        chunks = []
        start = 0
        for i in range(num_threads):
            # 为最后一个块分配余数
            chunk_size = base_chunk_size + (remainder if i == num_threads - 1 else 0)
            end = start + chunk_size - 1
            chunks.append((url, start, end, temp_dir, filename, session, i, num_threads, file_size))
            start = end + 1
        
        # 使用线程池下载
        print(f'   使用 {num_threads} 个线程下载 {filename}...')
        print(f'   文件总大小: {file_size / (1024*1024):.2f}MB')
        for i, (_, start, end, _, _, _, _, _, _) in enumerate(chunks):
            chunk_size = end - start + 1
            print(f'   块 {i+1} 大小: {chunk_size / (1024*1024):.2f}MB ({(chunk_size/file_size*100):.1f}%)')
        
        # 创建总进度条，使用固定宽度
        total_progress = tqdm(
            total=file_size,
            unit='iB',
            unit_scale=True,
            desc='总进度',
            position=0,
            leave=True,
            ncols=80
        )
        
        # 跟踪已下载的总大小
        downloaded_size = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(download_chunk, chunk): chunk for chunk in chunks}
            for future in concurrent.futures.as_completed(futures):
                chunk = futures[future]
                try:
                    temp_file = future.result()
                    chunk_size = os.path.getsize(temp_file)
                    downloaded_size += chunk_size
                    total_progress.update(chunk_size)
                except Exception as e:
                    print(f'   下载块 {chunk[6]+1} 时出错: {e}')
        
        total_progress.close()
        
        # 合并文件块
        print(f'   正在合并文件块...')
        merge_chunks(filename, [os.path.join(temp_dir, f"{os.path.basename(filename)}.part{i}") for i in range(num_threads)], temp_dir)
        
        # 验证下载的文件
        print(f'   正在验证下载的文件...')
        file_info = get_coco_file_info().get(os.path.basename(filename))
        if file_info:
            is_valid, message = verify_file_integrity(filename, file_info['size'], file_info['md5'])
            if is_valid:
                print(f'   ✓ 文件下载完成并验证通过: {filename}')
            else:
                print(f'   ✗ 文件验证失败: {message}')
                raise Exception("文件验证失败")
        else:
            print(f'   ✓ 文件下载完成: {filename}')
        
    finally:
        session.close()

def download_coco_dataset(dataDir, download_train=True, download_val=True):
    """
    下载COCO数据集
    
    参数:
        dataDir: 数据保存目录
        download_train: 是否下载训练集
        download_val: 是否下载验证集
    """
    print('\n=== COCO 2017 数据集下载流程 ===')
    print('1. 创建必要的目录结构')
    # 创建必要的目录
    os.makedirs(dataDir, exist_ok=True)
    os.makedirs(os.path.join(dataDir, 'annotations'), exist_ok=True)
    print(f'   目录已创建: {dataDir}')
    
    print('\n2. 下载标注文件')
    # 下载标注文件
    annotations_file = os.path.join(dataDir, 'annotations', 'instances_val2017.json')
    if os.path.exists(annotations_file):
        print('   ✓ 标注文件已存在，跳过下载')
    else:
        annotations_url = 'http://images.cocodataset.org/annotations/annotations_trainval2017.zip'
        print('   正在下载标注文件...')
        annotations_zip = os.path.join(dataDir, 'annotations.zip')
        try:
            download_file(annotations_url, annotations_zip)
            print('   正在解压标注文件...')
            with zipfile.ZipFile(annotations_zip, 'r') as zip_ref:
                zip_ref.extractall(dataDir)
            os.remove(annotations_zip)
            print('   ✓ 标注文件解压完成')
        except Exception as e:
            print(f'   ✗ 下载标注文件时出错: {e}')
            print('   你可以稍后重新运行脚本，下载将从断点处继续')

    if download_train:
        print('\n3. 下载训练集')
        train_dir = os.path.join(dataDir, 'train2017')
        if os.path.exists(train_dir):
            print('   ✓ 训练集已存在，跳过下载')
        else:
            print('   正在下载训练集...')
            train_url = 'http://images.cocodataset.org/zips/train2017.zip'
            train_zip = os.path.join(dataDir, 'train2017.zip')
            try:
                download_file(train_url, train_zip)
                print('   正在解压训练集...')
                with zipfile.ZipFile(train_zip, 'r') as zip_ref:
                    zip_ref.extractall(dataDir)
                os.remove(train_zip)
                print('   ✓ 训练集解压完成')
            except Exception as e:
                print(f'   ✗ 下载训练集时出错: {e}')
                print('   你可以稍后重新运行脚本，下载将从断点处继续')

    if download_val:
        print('\n4. 下载验证集')
        val_dir = os.path.join(dataDir, 'val2017')
        if os.path.exists(val_dir):
            print('   ✓ 验证集已存在，跳过下载')
        else:
            print('   正在下载验证集...')
            val_url = 'http://images.cocodataset.org/zips/val2017.zip'
            val_zip = os.path.join(dataDir, 'val2017.zip')
            try:
                download_file(val_url, val_zip)
                print('   正在解压验证集...')
                with zipfile.ZipFile(val_zip, 'r') as zip_ref:
                    zip_ref.extractall(dataDir)
                os.remove(val_zip)
                print('   ✓ 验证集解压完成')
            except Exception as e:
                print(f'   ✗ 下载验证集时出错: {e}')
                print('   你可以稍后重新运行脚本，下载将从断点处继续')

def parse_args():
    """
    解析命令行参数
    
    返回:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(description='COCO 2017数据集下载工具')
    parser.add_argument('--clean', action='store_true',
                      help='清理之前下载的内容，重新开始下载')
    parser.add_argument('--train-only', action='store_true',
                      help='只下载训练集')
    parser.add_argument('--val-only', action='store_true',
                      help='只下载验证集')
    return parser.parse_args()

def clean_coco_dataset(dataDir):
    """
    清理COCO数据集目录
    
    参数:
        dataDir: 数据目录路径
    """
    print('\n=== 清理COCO数据集目录 ===')
    try:
        # 要删除的文件和目录列表
        items_to_remove = [
            'train2017.zip',
            'val2017.zip',
            'annotations.zip',
            'train2017',
            'val2017',
            'annotations',
            'coco_sample_image.jpg'
        ]
        
        for item in items_to_remove:
            path = os.path.join(dataDir, item)
            if os.path.exists(path):
                if os.path.isfile(path):
                    print(f'   删除文件: {item}')
                    os.remove(path)
                elif os.path.isdir(path):
                    print(f'   删除目录: {item}')
                    shutil.rmtree(path)
        
        print('   ✓ 清理完成')
    except Exception as e:
        print(f'   ✗ 清理过程中出错: {e}')

class DownloadProgressGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("COCO数据集下载器")
        
        # 设置窗口大小和位置
        window_width = 800
        window_height = 600
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 设置窗口最小尺寸
        self.root.minsize(600, 400)
        
        # 配置网格权重，使窗口可调整大小
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding="20")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # 创建标题
        title_label = ttk.Label(
            self.main_frame,
            text="COCO 2017 数据集下载",
            font=('SF Pro Display', 20) if os.name == 'posix' else ('Helvetica', 20)
        )
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # 创建下载位置选择框架
        self.location_frame = ttk.LabelFrame(
            self.main_frame,
            text="下载位置",
            padding="15"
        )
        self.location_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        self.location_frame.grid_columnconfigure(0, weight=1)
        
        # 下载路径显示和选择
        self.path_var = tk.StringVar(value=os.path.expanduser("~/Downloads/coco"))
        self.path_entry = ttk.Entry(
            self.location_frame,
            textvariable=self.path_var,
            font=('SF Pro Text', 11) if os.name == 'posix' else ('Helvetica', 11)
        )
        self.path_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.browse_button = ttk.Button(
            self.location_frame,
            text="选择位置",
            command=self.browse_directory
        )
        self.browse_button.grid(row=0, column=1)
        
        # 创建进度条框架
        self.progress_frame = ttk.LabelFrame(
            self.main_frame,
            text="下载进度",
            padding="15"
        )
        self.progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        self.progress_frame.grid_columnconfigure(1, weight=1)
        
        # 总进度
        self.total_label = ttk.Label(
            self.progress_frame,
            text="总进度:",
            font=('SF Pro Text', 12) if os.name == 'posix' else ('Helvetica', 12)
        )
        self.total_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.total_progress = ttk.Progressbar(
            self.progress_frame,
            length=600,
            mode='determinate',
            style='Accent.TProgressbar'
        )
        self.total_progress.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        self.total_percent = ttk.Label(
            self.progress_frame,
            text="0%",
            font=('SF Pro Text', 12) if os.name == 'posix' else ('Helvetica', 12)
        )
        self.total_percent.grid(row=0, column=2, padx=5)
        
        # 块进度条
        self.chunk_progresses = []
        self.chunk_percents = []
        for i in range(4):
            chunk_label = ttk.Label(
                self.progress_frame,
                text=f"块 {i+1}:",
                font=('SF Pro Text', 11) if os.name == 'posix' else ('Helvetica', 11)
            )
            chunk_label.grid(row=i+1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
            
            progress = ttk.Progressbar(
                self.progress_frame,
                length=600,
                mode='determinate',
                style='Accent.TProgressbar'
            )
            progress.grid(row=i+1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            self.chunk_progresses.append(progress)
            
            percent = ttk.Label(
                self.progress_frame,
                text="0%",
                font=('SF Pro Text', 11) if os.name == 'posix' else ('Helvetica', 11)
            )
            percent.grid(row=i+1, column=2, padx=5, pady=5)
            self.chunk_percents.append(percent)
        
        # 状态信息
        self.status_frame = ttk.LabelFrame(
            self.main_frame,
            text="状态信息",
            padding="15"
        )
        self.status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_rowconfigure(0, weight=1)
        
        # 创建文本框和滚动条的容器
        text_container = ttk.Frame(self.status_frame)
        text_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_container.grid_columnconfigure(0, weight=1)
        text_container.grid_rowconfigure(0, weight=1)
        
        self.status_text = tk.Text(
            text_container,
            height=8,
            wrap=tk.WORD,
            font=('SF Pro Text', 11) if os.name == 'posix' else ('Helvetica', 11)
        )
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(
            text_container,
            orient=tk.VERTICAL,
            command=self.status_text.yview
        )
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.status_text['yscrollcommand'] = scrollbar.set
        
        # 控制按钮
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.grid(row=4, column=0, pady=(0, 10))
        
        # 创建按钮样式
        style = ttk.Style()
        if os.name == 'posix':  # macOS
            style.configure('Primary.TButton', font=('SF Pro Text', 12))
            style.configure('Secondary.TButton', font=('SF Pro Text', 12))
        else:  # Windows/Linux
            style.configure('Primary.TButton', font=('Helvetica', 12))
            style.configure('Secondary.TButton', font=('Helvetica', 12))
        
        # 主要按钮（开始/继续下载）
        self.download_button = ttk.Button(
            self.button_frame,
            text="开始下载",
            style='Primary.TButton',
            command=self.start_download
        )
        self.download_button.grid(row=0, column=0, padx=5)
        
        # 清理按钮
        self.clean_button = ttk.Button(
            self.button_frame,
            text="清理缓存",
            style='Secondary.TButton',
            command=self.clean_cache
        )
        self.clean_button.grid(row=0, column=1, padx=5)
        
        # 消息队列
        self.queue = queue.Queue()
        
        # 启动更新线程
        self.update_thread = threading.Thread(target=self.update_gui)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        # 设置窗口关闭事件处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 启用按钮
        self.set_buttons_state(tk.NORMAL)
    
    def browse_directory(self):
        """选择下载目录"""
        directory = filedialog.askdirectory(
            title="选择下载位置",
            initialdir=self.path_var.get()
        )
        if directory:
            self.path_var.set(directory)
    
    def get_download_path(self):
        """获取下载路径"""
        path = self.path_var.get()
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    
    def start_download(self):
        """开始或继续下载"""
        self.set_buttons_state(tk.DISABLED)
        # 检查已下载的内容，决定下载内容
        download_path = self.get_download_path()
        download_train = not os.path.exists(os.path.join(download_path, 'train2017'))
        download_val = not os.path.exists(os.path.join(download_path, 'val2017'))
        
        if download_train or download_val:
            self.queue.put({'type': 'status', 'text': '检测到未完成下载，将继续下载...'})
        threading.Thread(target=self._download, args=(download_path, False, download_train, download_val)).start()
    
    def clean_cache(self):
        """清理缓存"""
        if messagebox.askyesno("确认清理", "确定要清理所有已下载的内容吗？\n这将删除所有已下载的文件。"):
            self.set_buttons_state(tk.DISABLED)
            download_path = self.get_download_path()
            threading.Thread(target=self._clean_and_download, args=(download_path,)).start()
    
    def _clean_and_download(self, download_path):
        """清理并开始下载"""
        try:
            self.queue.put({'type': 'status', 'text': '正在清理缓存...'})
            clean_coco_dataset(download_path)
            self.queue.put({'type': 'status', 'text': '缓存清理完成，开始下载...'})
            self._download(download_path, False, True, True)
        except Exception as e:
            self.queue.put({'type': 'status', 'text': f'清理出错: {str(e)}'})
        finally:
            self.queue.put({'type': 'download_complete'})
    
    def _download(self, download_path, clean, download_train, download_val):
        """执行下载"""
        try:
            if clean:
                self.queue.put({'type': 'status', 'text': '正在清理之前下载的内容...'})
                clean_coco_dataset(download_path)
            
            self.queue.put({'type': 'status', 'text': '开始下载数据集...'})
            if download_train:
                self.queue.put({'type': 'status', 'text': '将下载训练集（约18GB）...'})
            if download_val:
                self.queue.put({'type': 'status', 'text': '将下载验证集（约815MB）...'})
            
            download_coco_dataset(download_path, download_train, download_val)
            self.queue.put({'type': 'status', 'text': '下载完成！'})
        except Exception as e:
            self.queue.put({'type': 'status', 'text': f'下载出错: {str(e)}'})
        finally:
            self.queue.put({'type': 'download_complete'})
    
    def set_buttons_state(self, state):
        """设置按钮状态"""
        self.download_button['state'] = state
        self.clean_button['state'] = state
        self.browse_button['state'] = state
    
    def on_closing(self):
        """处理窗口关闭事件"""
        if messagebox.askokcancel("退出", "确定要退出吗？\n如果正在下载，下载将会中断。"):
            self.root.destroy()
    
    def update_gui(self):
        """更新GUI显示"""
        while True:
            try:
                msg = self.queue.get_nowait()
                if msg['type'] == 'progress':
                    # 更新进度条
                    if msg['chunk_id'] == -1:  # 总进度
                        self.total_progress['value'] = msg['progress']
                        self.total_percent['text'] = f"{msg['progress']:.1f}%"
                    else:  # 块进度
                        self.chunk_progresses[msg['chunk_id']]['value'] = msg['progress']
                        self.chunk_percents[msg['chunk_id']]['text'] = f"{msg['progress']:.1f}%"
                elif msg['type'] == 'status':
                    # 更新状态信息
                    self.status_text.insert(tk.END, msg['text'] + '\n')
                    self.status_text.see(tk.END)
                elif msg['type'] == 'download_complete':
                    # 下载完成，启用按钮
                    self.set_buttons_state(tk.NORMAL)
            except queue.Empty:
                self.root.update()
                time.sleep(0.1)
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()

# 主程序使用说明
"""
使用方法：
1. 基本用法（支持断点续传）：
   python download_coco.py

2. 清理之前的内容并重新下载：
   python download_coco.py --clean

3. 只下载训练集：
   python download_coco.py --train-only

4. 只下载验证集：
   python download_coco.py --val-only

5. 清理并只下载训练集：
   python download_coco.py --clean --train-only

参数说明：
--clean       : 清理之前下载的内容，重新开始下载
--train-only  : 只下载训练集，不下载验证集
--val-only    : 只下载验证集，不下载训练集

注意事项：
1. 默认情况下支持断点续传，如果下载中断，直接重新运行脚本即可继续下载
2. 使用--clean参数会删除所有已下载的内容，请谨慎使用
3. 下载过程中会自动验证文件完整性，如果发现文件损坏会自动重新下载
4. 下载完成后会自动解压并删除压缩文件
5. 建议使用稳定的网络连接，避免频繁中断

输出说明：
- ✓ 表示操作成功
- ✗ 表示操作失败
- ⚠ 表示警告信息
"""

if __name__ == '__main__':
    # 创建GUI实例
    gui = DownloadProgressGUI()
    
    # 运行GUI
    gui.run()