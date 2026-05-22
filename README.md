# my_script

个人 Python 脚本与工具集，用于日常文件管理、目录整理及文档维护。

---

## 目录结构

```
my_script/
├── tools/          # 通用工具脚本（文件夹管理、README 生成等）
├── scripts/        # 其他独立功能脚本
└── requirements.txt
```

## 使用方式

各脚本独立运行，无需虚拟环境，直接使用系统 Python：

```bash
python scripts/xxx.py
python tools/xxx.py
```

如有依赖，先安装：

```bash
pip install -r requirements.txt
```

---

## 修改记录

| 版本   | 日期         | 修改内容      |
|--------|------------|-------------|
| v1.0   | 2026/05/22 | 初始化仓库结构 |
