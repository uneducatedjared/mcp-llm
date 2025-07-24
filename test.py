import onnxruntime as ort

# 检查版本
print(f"ONNX Runtime版本: {ort.__version__}")

# 测试基本功能
# session = ort.InferenceSession("model.onnx")  # 替换为有效模型路径
print("推理会话创建成功！")