import sys

import torch


print(f"PYTHON_VERSION={sys.version}")
print(f"TORCH_VERSION={torch.__version__}")
print(f"CUDA_AVAILABLE={'true' if torch.cuda.is_available() else 'false'}")

if not torch.cuda.is_available():
    raise RuntimeError("RHOMBUS_GPU_SMOKE_NO_CUDA")

print(f"GPU_NAME={torch.cuda.get_device_name(0)}")
print(f"GPU_COUNT={torch.cuda.device_count()}")
print("RHOMBUS_GPU_SMOKE=PASS")
