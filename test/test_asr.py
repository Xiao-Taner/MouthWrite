import base64
import requests
import os
from openai import OpenAI

# 1. 配置连接信息
client = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=os.environ.get("DASHSCOPE_API_KEY", "your-api-key-here")
)

local_filename = "asr_zh.wav"


# 3. 将本地文件转换为 Base64 字符串
# 这是最关键的一步！这样模型就不需要自己去上网下载了
def encode_audio(file_path):
    with open(file_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode('utf-8')

base64_audio = encode_audio(local_filename)
data_url = f"data:audio/wav;base64,{base64_audio}"

# 4. 发送请求
print("正在识别中 (通过 Base64 传输)...")
try:
    response = client.chat.completions.create(
        model="fun-asr-realtime",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "audio_url", "audio_url": {"url": data_url}}
                ]
            }
        ]
    )

    # 5. 打印结果 (增加判空保护)
    if response.choices:
        print("识别结果：", response.choices[0].message.content)
    else:
        print("❌ 错误：模型返回了空结果。请检查服务端日志。")
        print("完整响应内容：", response)

except Exception as e:
    print(f"❌ 请求发生异常: {e}")