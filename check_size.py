import os
path = r"e:\YADISK\Yandex.Disk\Code\WB_packer_vscode\dist\WB_packer.exe"
if os.path.exists(path):
    size = os.path.getsize(path)
    print(f"Размер: {size:,} байт ({size/1024/1024:.2f} МБ)")
else:
    print("Файл не найден!")
