import pyaudio
import wave
import base64
import threading
from openai import OpenAI

# ================= 配置区域 =================
# WSL2 的地址 (vLLM 服务)
API_BASE = "http://localhost:8000/v1"
API_KEY = "EMPTY"
MODEL_NAME = "Qwen/Qwen3-ASR-1.7B"

# 录音配置
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Qwen3-ASR 推荐 16k 采样率
WAVE_OUTPUT_FILENAME = "temp_record.wav"
# ===========================================

def record_audio():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS,
                    rate=RATE, input=True,
                    frames_per_buffer=CHUNK)

    print("\n🎤 正在录音... (按下回车键停止)")
    frames = []
    
    # 使用一个标志位来控制录音线程
    is_recording = True

    def input_thread():
        nonlocal is_recording
        input() # 等待用户按回车
        is_recording = False

    # 启动监听键盘的线程
    threading.Thread(target=input_thread).start()

    while is_recording:
        data = stream.read(CHUNK)
        frames.append(data)

    print("🛑 录音结束，正在发送给 AI...")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def audio_to_base64(file_path):
    with open(file_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode('utf-8')

def call_qwen_asr():
    client = OpenAI(base_url=API_BASE, api_key=API_KEY)
    
    # 把音频文件转为 Base64 字符串，这样无需上传文件实体
    base64_audio = audio_to_base64(WAVE_OUTPUT_FILENAME)
    data_url = f"data:audio/wav;base64,{base64_audio}"

    try:
        # 发起流式请求 (stream=True)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": "请将这段语音转录为文字："}, # 可选的 Prompt
                        {"type": "image_url", "image_url": {"url": data_url}} # vLLM这里借用了image_url的字段传音频
                    ]
                }
            ],
            stream=True, # <--- 关键：开启流式输出
            temperature=0.0 # ASR 不需要创造性，温度设为0最准
        )

        print("\n📝 识别结果：")
        print("-" * 30)
        
        full_text = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True) # 打字机效果
                full_text += content
        
        print("\n" + "-" * 30 + "\n")
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        print("提示：请检查 WSL2 中的 vLLM 服务是否正在运行，且端口是 8000。")

if __name__ == "__main__":
    while True:
        choice = input("按回车开始录音 (输入 'q' 退出): ")
        if choice.lower() == 'q':
            break
        
        record_audio()
        call_qwen_asr()