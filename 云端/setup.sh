#!/bin/bash
# Claude Code 云端环境的 setup script：在环境设置里粘贴本文件内容，或写 `bash 云端/setup.sh`。
set -e
sudo apt-get update -qq
sudo apt-get install -y -qq fonts-noto-cjk fonts-arphic-ukai fonts-arphic-uming libreoffice-writer libreoffice-impress poppler-utils >/dev/null
pip install -q python-docx pypdf openpyxl pdfplumber python-pptx
echo "云端环境就绪：中文字体(Noto CJK/文鼎楷体)、LibreOffice、poppler、python-docx"
