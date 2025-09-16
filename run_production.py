#!/usr/bin/env python3
"""
ملف تشغيل خادم Q8 Downloader في بيئة الإنتاج
"""

import os
import sys

# إضافة مسار المشروع
sys.path.insert(0, os.path.dirname(__file__))

from src.main import app

if __name__ == '__main__':
    # تشغيل الخادم في بيئة الإنتاج
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )

