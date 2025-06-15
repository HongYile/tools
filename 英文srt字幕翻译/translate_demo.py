"""
火山引擎风格的字幕翻译脚本
"""

import os
import time
from openai import OpenAI
from tqdm import tqdm

client = OpenAI(
    api_key="AccessKey",  # 请替换成您的AccessKey
    base_url="https://ark.cn-beijing.volces.com/api/v3"
    )

def translate_text(text, max_retries=3, timeout=30):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="doubao-1-5-pro-32k-250115",
                messages=[
                    {"role": "system", "content": "你是一个专业的字幕翻译助手。请将以下英文文本翻译成中文，保持原文的格式和换行。注意：多行文本可能是一个完整的句子，请确保翻译的连贯性。只返回翻译结果，不要添加任何解释。"},
                    {"role": "user", "content": text}
                ],
                timeout=timeout
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 2)
            else:
                return text

def process_srt_file(input_file, output_file):
    print(f"正在处理文件: {input_file}")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return
    
    # 按字幕块分割
    subtitle_blocks = content.strip().split('\n\n')
    total_blocks = len(subtitle_blocks)
    
    if total_blocks == 0:
        print("没有找到有效的字幕块")
        return
    
    # 创建或清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('')
    
    # 使用tqdm创建进度条
    for i, block in enumerate(tqdm(subtitle_blocks, desc="翻译进度")):
        try:
            lines = block.split('\n')
            if len(lines) < 3:  # 跳过无效块
                continue
                
            # 前两行是序号和时间码，保持不变
            header = '\n'.join(lines[:2])
            
            # 剩余行是字幕文本
            subtitle_text = '\n'.join(lines[2:])
            
            # 翻译字幕文本
            translated_text = translate_text(subtitle_text)
            
            # 组合翻译后的块
            translated_block = f"{header}\n{translated_text}"
            
            # 写入文件
            with open(output_file, 'a', encoding='utf-8') as f:
                if i > 0:  # 如果不是第一个块，添加空行
                    f.write('\n\n')
                f.write(translated_block)
                
        except Exception as e:
            continue

    print(f"翻译完成！输出文件：{output_file}")

# 使用示例
input_srt = "CUDA Programming Course – High-Performance Computing with GPUs.srt"  # 输入字幕文件名 英文
output_srt = "CUDA Programming Course – High-Performance Computing with GPUs cn.srt"

process_srt_file(input_srt, output_srt)