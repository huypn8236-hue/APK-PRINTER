[app]
# Tên app hiển thị
title = Order Printer

# Tên package (unique, bạn có thể đổi)
package.name = orderprinter
package.domain = org.example

# File main
source.dir = .
source.include_exts = py,png,jpg,jpeg,ttf,xml,json
main.py = APK.py

# Icon (nếu có file icon.png thì đặt cùng thư mục)
icon.filename = %(source.dir)s/icon.png

# Phiên bản
version = 1.0.0

# Orientation mặc định
orientation = portrait

# Không fullscreen
fullscreen = 0

# Các thư viện cần thiết
requirements = python3,kivy,reportlab,pyjnius

# Quyền Android (Bluetooth + Storage)
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,ACCESS_FINE_LOCATION,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# Nếu bạn dùng font riêng (arial.ttf) thì để cùng folder và include
android.add_assets = arial.ttf,*.json,*.pdf

# Presplash (màn hình chờ khi mở app) → tuỳ chọn
presplash.filename = %(source.dir)s/presplash.png
android.presplash_color = #FFFFFF

# Target API
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21

# Kiến trúc CPU hỗ trợ
android.archs = arm64-v8a,armeabi-v7a

# Nhánh p4a
p4a.branch = master

# Cho phép backup
android.allow_backup = True

# Loại bỏ file rác
exclude_patterns = tests,docs,*.pyc,*.pyo,*.md

[buildozer]
log_level = 2
warn_on_root = 1
