[app]
# --- Thông tin ứng dụng ---
title = Order Printer
package.name = orderprinter
package.domain = org.example

# --- File nguồn ---
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,xml,json
icon.filename = %(source.dir)s/icon.png

# --- Phiên bản ---
version = 1.0.0

# --- Hiển thị ---
orientation = portrait
fullscreen = 0

# --- Thư viện yêu cầu ---
# ⚡ Dành riêng cho Android (Bluetooth + giao diện Kivy)
requirements = python3,kivy,pyjnius,pillow

# --- Quyền Android ---
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,ACCESS_FINE_LOCATION,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# --- Tài nguyên đính kèm ---
android.add_assets = arial.ttf
# ⚠️ Không cần *.pdf — PDF được tạo runtime, không nên đóng gói sẵn

# --- Màn hình khởi động ---
presplash.filename = %(source.dir)s/icon.png
android.presplash_color = #FFFFFF

# --- Android SDK / NDK ---
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a,armeabi-v7a

# ⚙️ Dùng nhánh ổn định để tránh lỗi pip/setup.py
p4a.branch = develop

# Lý do:
# - "develop" ổn định hơn "master" khi build trên CI (GitHub Actions)
# - Đã fix các lỗi setuptools/pip >= 24.x và gradle 8.x
# - "master" thường bị lỗi build khi Google cập nhật NDK/SDK mới

android.allow_backup = True

# --- Giảm kích thước APK ---
exclude_patterns = tests,docs,*.pyc,*.pyo,*.md,__pycache__,.git

# --- Môi trường ---
environment = 
    PYTHONOPTIMIZE=2
    KIVY_METRICS_DENSITY=2

[buildozer]
log_level = 2
warn_on_root = 1
android.accept_sdk_license = True
android.enable_androidx = True
