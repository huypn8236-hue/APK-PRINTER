# order_printer_app_kivy.py
# Full app (PC: create/open PDF) (Android: preview + ESC/POS Bluetooth printing)
# 2025-09-28
import os
import sys
import json
import time
import traceback
import subprocess
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform  # <-- accurate platform detection for Kivy

# ---------- CONFIG ----------
HISTORY_FILE = "print_history.json"

# ---------- HISTORY UTIL ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(h):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Warning: cannot save history:", e)

def add_history_entry(order_id, customer, box_qty):
    h = load_history()
    h.append({
        "order_id": str(order_id),
        "customer": str(customer),
        "box_qty": int(box_qty),
        "timestamp": datetime.now().isoformat()
    })
    save_history(h)

def has_been_printed(order_id):
    h = load_history()
    return any(item.get("order_id") == str(order_id) for item in h)

# ---------- PDF CREATE (Desktop) ----------
# Using reportlab to generate 70x50 mm pages (one per BOX)
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAGE_W_MM = 70
PAGE_H_MM = 50
MARGIN_MM = 5
FONT_TTF = "arial.ttf"  # optional bundled font
FONT_NAME = "Helvetica"
FONT_NAME1 = "Helvetica-Bold"
if os.path.exists(FONT_TTF):
    try:
        pdfmetrics.registerFont(TTFont("AppFont", FONT_TTF))
        FONT_NAME = "AppFont"
    except:
        FONT_NAME = "Helvetica"

def create_pdf_80x50_left(order_id, customer, box_qty):
    """Create PDF file ORDER_<order_id>.pdf with box_qty pages."""
    pagesize = (PAGE_W_MM * mm, PAGE_H_MM * mm)
    filename = f"ORDER_{order_id}.pdf"
    try:
        c = canvas.Canvas(filename, pagesize=pagesize)
        margin = MARGIN_MM * mm
        width, height = pagesize
        usable_h = height - 2 * margin
        part_h = usable_h / 3.0
        left_x = margin
        for i in range(int(box_qty)):
            order_font = max(10, min(int(part_h * 0.8), 48))
            other_font = max(8, min(int(part_h * 0.45), 30))
            y1 = height - margin - (part_h * 0.3)
            c.setFont(FONT_NAME1, order_font)
            text1 = str(order_id)
            max_chars_line = int((width - 2.5 * margin) / (order_font * 0.6)) if order_font > 0 else 40
            if len(text1) > max_chars_line:
                text1 = text1[:max_chars_line]
            c.drawString(left_x, y1, text1)
            y2 = height - margin - part_h - (part_h * 0.3)
            c.setFont(FONT_NAME, other_font)
            text2 = str(customer)
            max_chars_line2 = int((width - 2.5 * margin) / (other_font * 0.5)) if other_font > 0 else 40
            if len(text2) > max_chars_line2:
                text2 = text2[:max_chars_line2]
            c.drawString(left_x, y2, text2)
            y3 = height - margin - part_h * 2.5 - (part_h * 0.3)
            c.setFont(FONT_NAME, other_font)
            text3 = f"BOX: # {i + 1} / {box_qty}"
            c.drawString(left_x, y3, text3)
            c.showPage()
        c.save()
        return filename
    except Exception:
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except:
            pass
        raise

# ---------- OPEN PDF (Desktop) ----------
def open_pdf_by_platform(path):
    """Open PDF using OS default application (desktop only)."""
    abs_path = os.path.abspath(path)
    try:
        if platform == "win":
            os.startfile(abs_path)
        elif platform == "macosx":
            subprocess.call(["open", abs_path])
        else:
            # linux
            subprocess.call(["xdg-open", abs_path])
    except Exception as e:
        print("open_pdf error:", e)

# ---------- Platform helper ----------
def is_android():
    """Return True when running on Android (Kivy/p4a)."""
    return platform == "android"

# ---------- ESC/POS bytes builder ----------
def escpos_bytes_for_label(order_id, customer, box_index, box_total, encoding='utf-8'):
    """
    Build ESC/POS bytes for a label.
    Basic format:
      - reset
      - enlarge order_id
      - normal customer
      - BOX line
      - feeds + cut
    NOTE: Each printer differs; adjust sequences to your printer manual.
    """
    b = bytearray()
    b += b'\x1b\x40'  # reset
    # Order ID
    b += b'\x1d\x21\x11'
    b += order_id.encode(encoding, errors='replace') + b'\n'
    # Customer
    b += b'\x1d\x21\x00'
    b += customer.encode(encoding, errors='replace') + b'\n'
    # Box info
    b += f"BOX: #{box_index}/{box_total}\n".encode(encoding)
    b += b'\n\n'
    b += b'\x1d\x56\x00'
    return bytes(b)

# ---------- pyjnius Bluetooth helpers (Android) ----------
def find_paired_printers_pyjnius():
    """Return list of (name, mac) for bonded devices. Best-effort."""
    try:
        from jnius import autoclass
        BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            return []
        paired = adapter.getBondedDevices()
        devices = []
        # paired could be a Java Set - try toArray then iterate
        try:
            arr = paired.toArray()
            for dev in arr:
                try:
                    devices.append((dev.getName(), dev.getAddress()))
                except:
                    continue
        except:
            try:
                it = paired.iterator()
                while it.hasNext():
                    dev = it.next()
                    try:
                        devices.append((dev.getName(), dev.getAddress()))
                    except:
                        continue
            except Exception:
                pass
        return devices
    except Exception as e:
        print("find_paired_printers_pyjnius error:", e)
        return []

def print_via_bluetooth_pyjnius(mac_addr, payload_bytes, timeout=10):
    """Connect via RFCOMM SPP UUID and send bytes. Returns (True, None) or (False, error)."""
    try:
        from jnius import autoclass
        UUID = autoclass('java.util.UUID')
        BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
        adapter = BluetoothAdapter.getDefaultAdapter()
        if adapter is None:
            return False, "Bluetooth adapter not available"

        device = adapter.getRemoteDevice(mac_addr)
        spp_uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        socket = device.createRfcommSocketToServiceRecord(spp_uuid)
        try:
            if adapter.isDiscovering():
                adapter.cancelDiscovery()
        except:
            pass
        socket.connect()
        out = socket.getOutputStream()
        out.write(payload_bytes)
        out.flush()
        try:
            out.close()
        except:
            pass
        try:
            socket.close()
        except:
            pass
        return True, None
    except Exception as e:
        # fallback reflection trick for some devices
        try:
            from jnius import autoclass
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            adapter = BluetoothAdapter.getDefaultAdapter()
            device = adapter.getRemoteDevice(mac_addr)
            klass = device.getClass()
            Integer = autoclass('java.lang.Integer')
            m = klass.getMethod("createRfcommSocket", [Integer.TYPE])
            sock = m.invoke(device, 1)
            sock.connect()
            out = sock.getOutputStream()
            out.write(payload_bytes)
            out.flush()
            out.close()
            sock.close()
            return True, None
        except Exception as e2:
            return False, f"{e} ; fallback: {e2}"

# ---------- Best-effort runtime permission request (Android) ----------
def request_android_permissions():
    """
    Try to request Bluetooth permissions at runtime.
    This is best-effort: declare permissions in buildozer.spec too.
    """
    if not is_android():
        return False, "not android"
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        Build = autoclass('android.os.Build')
        sdk = int(Build.VERSION.SDK)
        if sdk >= 23:
            Manifest = autoclass('android.Manifest$permission')
            perms = []
            # include common ones; some may not exist on older SDKs
            try:
                perms.append(Manifest.BLUETOOTH)
                perms.append(Manifest.BLUETOOTH_ADMIN)
            except:
                pass
            try:
                perms.append(Manifest.BLUETOOTH_CONNECT)
                perms.append(Manifest.BLUETOOTH_SCAN)
            except:
                pass
            try:
                perms.append(Manifest.ACCESS_FINE_LOCATION)
            except:
                pass
            # build Java string array
            String = autoclass('java.lang.String')
            StringArray = autoclass('[Ljava.lang.String;')
            jarr = StringArray(len(perms))
            for i, p in enumerate(perms):
                jarr[i] = p
            activity.requestPermissions(jarr, 0)
        return True, None
    except Exception as e:
        print("request_android_permissions error:", e)
        return False, str(e)

# ---------- UI SCREENS ----------
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(12))
        inner = BoxLayout(orientation='vertical', size_hint=(.8, None), height=dp(420), spacing=dp(12),
                          pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.entry_order = TextInput(hint_text="Mã đơn hàng", font_size=dp(20), size_hint_y=None, height=dp(50))
        self.entry_customer = TextInput(hint_text="Tên khách", font_size=dp(20), size_hint_y=None, height=dp(50))
        self.entry_box = TextInput(hint_text="Số BOX", font_size=dp(20), size_hint_y=None, height=dp(50), input_filter='int')
        btn_print = Button(text="Xem & In", size_hint_y=None, height=dp(60), font_size=dp(20), background_color=[0.3, 0.6, 1, 1])
        btn_print.bind(on_release=self.on_print)
        btn_history = Button(text="Lịch sử đơn đã in", size_hint_y=None, height=dp(60), font_size=dp(20), background_color=[0.3, 1, 0.5, 1])
        btn_history.bind(on_release=lambda *_: setattr(self.manager, "current", "history"))
        btn_dupes = Button(text="Đơn bị in trùng", size_hint_y=None, height=dp(60), font_size=dp(20), background_color=[1, 0.5, 0.3, 1])
        btn_dupes.bind(on_release=lambda *_: setattr(self.manager, "current", "dupes"))
        inner.add_widget(self.entry_order)
        inner.add_widget(self.entry_customer)
        inner.add_widget(self.entry_box)
        inner.add_widget(btn_print)
        inner.add_widget(btn_history)
        inner.add_widget(btn_dupes)
        layout.add_widget(inner)
        self.add_widget(layout)

    def on_print(self, *_):
        oid = self.entry_order.text.strip()
        cust = self.entry_customer.text.strip()
        box = self.entry_box.text.strip()
        if not oid or not cust or not box:
            from kivy.uix.popup import Popup
            Popup(title="Thiếu thông tin", content=Label(text="Vui lòng nhập đầy đủ thông tin!"), size_hint=(.8, .4)).open()
            return
        try:
            box_n = int(box)
            if box_n <= 0:
                raise ValueError
        except:
            from kivy.uix.popup import Popup
            Popup(title="Sai định dạng", content=Label(text="Số BOX phải là số nguyên dương"), size_hint=(.8, .4)).open()
            return
        if has_been_printed(oid):
            from kivy.uix.popup import Popup
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.button import Button
            boxl = BoxLayout(orientation='vertical', spacing=dp(12))
            boxl.add_widget(Label(text=f"Đơn {oid} đã được in trước đó. Có chắc muốn in lại?"))
            btnl = BoxLayout(spacing=dp(12))
            popup = Popup(title="Đơn trùng", content=boxl, size_hint=(.8, .4))
            def yes(*_):
                popup.dismiss()
                self.do_print(oid, cust, box_n)
            def no(*_):
                popup.dismiss()
            btn_yes = Button(text="Có", on_release=yes)
            btn_no = Button(text="Không", on_release=no)
            btnl.add_widget(btn_yes)
            btnl.add_widget(btn_no)
            boxl.add_widget(btnl)
            popup.open()
            return
        self.do_print(oid, cust, box_n)

    def do_print(self, oid, cust, box_n):
        """
        Main dispatcher:
        - If desktop -> create PDF, save history, open file.
        - If Android -> request permissions + show preview popup which drives printing.
        """
        try:
            if not is_android():
                # Desktop behavior: create PDF, save history, open
                pdf_path = create_pdf_80x50_left(oid, cust, box_n)
                add_history_entry(oid, cust, box_n)
                open_pdf_by_platform(pdf_path)
                from kivy.uix.popup import Popup
                Popup(title="Hoàn tất", content=Label(text=f"Đã tạo {pdf_path} và mở để in/kiểm tra."), size_hint=(.8, .4)).open()
            else:
                # Android behavior: preview inside app + Bluetooth ESC/POS printing
                try:
                    request_android_permissions()
                except:
                    pass
                android_show_print_review_and_print(self, oid, cust, box_n)
            # reset inputs
            try:
                self.entry_order.text = self.entry_customer.text = self.entry_box.text = ""
            except:
                pass
        except Exception as e:
            traceback.print_exc()
            from kivy.uix.popup import Popup
            Popup(title="Lỗi", content=Label(text=str(e)), size_hint=(.8, .4)).open()

class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation='vertical', padding=dp(12))
        scroll = ScrollView()
        self.container = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter('height'))
        scroll.add_widget(self.container)
        btn_back = Button(text="Về trang chủ", size_hint_y=None, height=dp(50), font_size=dp(18), background_color=[0.6, 0.6, 0.6, 1])
        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(scroll)
        root.add_widget(btn_back)
        self.add_widget(root)

    def on_enter(self, *args):
        self.refresh_history()

    def refresh_history(self):
        self.container.clear_widgets()
        data = load_history()
        counts = {}
        for it in data:
            oid = it.get("order_id")
            counts[oid] = counts.get(oid, 0) + 1
        for it in reversed(data):
            oid = it.get("order_id")
            color = [1, 0, 0, 1] if counts.get(oid, 0) > 1 else [0, 0, 0.5, 1]
            lbl = Label(text=f"{it.get('order_id')} | {it.get('customer')} | BOX {it.get('box_qty')} | {it.get('timestamp')}",
                        size_hint_y=None, height=dp(40), color=color, font_size=dp(18))
            self.container.add_widget(lbl)

class DupesScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation='vertical', padding=dp(12))
        scroll = ScrollView()
        self.container = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter('height'))
        scroll.add_widget(self.container)
        btn_back = Button(text="Về trang chủ", size_hint_y=None, height=dp(50), font_size=dp(18), background_color=[0.6, 0.6, 0.6, 1])
        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(scroll)
        root.add_widget(btn_back)
        self.add_widget(root)

    def on_enter(self, *args):
        self.refresh_dupes()

    def refresh_dupes(self):
        self.container.clear_widgets()
        data = load_history()
        counts = {}
        for it in data:
            oid = it.get("order_id")
            counts[oid] = counts.get(oid, 0) + 1
        for oid, cnt in counts.items():
            if cnt > 1:
                lbl = Label(text=f"{oid} | số lần in: {cnt}", size_hint_y=None, height=dp(40), color=[1, 0, 0, 1], font_size=dp(18))
                self.container.add_widget(lbl)

# ---------- Android preview & print UI ----------
def android_show_print_review_and_print(self, oid, cust, box_n):
    """
    On Android:
    - Show scrollable previews for all BOXes (one preview per BOX).
    - Buttons: In (choose paired printer or enter MAC) / Hủy.
    - On In: send ESC/POS bytes for each BOX via Bluetooth using pyjnius helpers.
    - Save history only if >=1 success.
    """
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput

    root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
    scroll = ScrollView(size_hint=(1, None), size=(Window.width * 0.9, Window.height * 0.6))
    container = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=dp(6))
    container.bind(minimum_height=container.setter('height'))

    for i in range(box_n):
        preview = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(120), padding=dp(8), spacing=dp(4))
        lbl_order = Label(text=oid, font_size=28, size_hint_y=None, height=dp(40), halign='left', valign='middle')
        lbl_order.bind(size=lbl_order.setter('text_size'))
        lbl_cust = Label(text=cust, font_size=18, size_hint_y=None, height=dp(36), halign='left', valign='middle')
        lbl_cust.bind(size=lbl_cust.setter('text_size'))
        lbl_box = Label(text=f"BOX: #{i+1} / {box_n}", font_size=18, size_hint_y=None, height=dp(36), halign='left', valign='middle')
        lbl_box.bind(size=lbl_box.setter('text_size'))
        preview.add_widget(lbl_order)
        preview.add_widget(lbl_cust)
        preview.add_widget(lbl_box)
        container.add_widget(preview)

    scroll.add_widget(container)
    root.add_widget(scroll)

    status = Label(text="", size_hint_y=None, height=dp(30))
    root.add_widget(status)

    btn_row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
    btn_print = Button(text="In", font_size=18)
    btn_cancel = Button(text="Hủy", font_size=18)
    btn_row.add_widget(btn_print)
    btn_row.add_widget(btn_cancel)
    root.add_widget(btn_row)

    popup = Popup(title="Xem trước nhãn", content=root, size_hint=(0.95, 0.9))

    def do_print_action(*_):
        # Get paired devices
        printers = find_paired_printers_pyjnius()
        if not printers:
            status.text = "Không tìm thấy máy in đã ghép đôi. Nhập MAC hoặc ghép đôi trước."
            mac_box = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
            mac_input = TextInput(hint_text="MAC máy in (ví dụ: 00:11:22:33:44:55)", size_hint_x=0.8)
            mac_btn = Button(text="OK", size_hint_x=0.2)
            def mac_ok(*__):
                mac = mac_input.text.strip()
                if mac:
                    try:
                        popup.content.remove_widget(mac_box)
                    except:
                        pass
                    status.text = "Bắt đầu in..."
                    _print_sequence(mac)
                else:
                    status.text = "MAC rỗng"
            mac_btn.bind(on_release=mac_ok)
            mac_box.add_widget(mac_input)
            mac_box.add_widget(mac_btn)
            popup.content.add_widget(mac_box)
            return

        # If multiple printers, let user choose; otherwise use the only one
        if len(printers) > 1:
            sel_box = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
            sel_scroll = ScrollView(size_hint=(1, None), size=(Window.width * 0.9, dp(200)))
            sel_container = BoxLayout(orientation='vertical', size_hint_y=None)
            sel_container.bind(minimum_height=sel_container.setter('height'))
            choose_popup = None
            def make_choice_button(name, mac):
                btn = Button(text=f"{name} [{mac}]", size_hint_y=None, height=dp(48))
                def on_choose(_):
                    if choose_popup:
                        choose_popup.dismiss()
                    status.text = f"In tới {mac}..."
                    _print_sequence(mac)
                btn.bind(on_release=on_choose)
                return btn
            for name, mac in printers:
                sel_container.add_widget(make_choice_button(name or "Unknown", mac))
            sel_scroll.add_widget(sel_container)
            sel_box.add_widget(sel_scroll)
            choose_popup = Popup(title="Chọn máy in", content=sel_box, size_hint=(0.9, 0.6))
            choose_popup.open()
            return

        chosen = printers[0]
        status.text = f"In tới: {chosen[0]} [{chosen[1]}]..."
        _print_sequence(chosen[1])

    def _print_sequence(mac):
        success_count = 0
        fail_count = 0
        err_msgs = []
        for i in range(box_n):
            payload = escpos_bytes_for_label(oid, cust, i + 1, box_n)
            ok, err = print_via_bluetooth_pyjnius(mac, payload)
            time.sleep(0.15)  # small gap
            if ok:
                success_count += 1
            else:
                fail_count += 1
                err_msgs.append(f"#{i+1}: {err}")
        if success_count > 0:
            add_history_entry(oid, cust, box_n)
        res = f"In xong: {success_count} thành công, {fail_count} lỗi."
        if err_msgs:
            res += "\n" + "\n".join(err_msgs[:5])
        status.text = res

    def cancel(*_):
        popup.dismiss()

    btn_print.bind(on_release=do_print_action)
    btn_cancel.bind(on_release=cancel)
    popup.open()

# ---------- App ----------
class OrderPrinterApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(HistoryScreen(name="history"))
        sm.add_widget(DupesScreen(name="dupes"))
        return sm

if __name__ == "__main__":
    OrderPrinterApp().run()

# ---------- BUILD / PERMISSIONS NOTES (copy to buildozer.spec) ----------
# requirements = python3,kivy,pyjnius,reportlab
# android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_CONNECT, BLUETOOTH_SCAN, ACCESS_FINE_LOCATION, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE
#
# Notes:
# - platform detection uses kivy.utils.platform (values: 'win', 'linux', 'macosx', 'android').
# - On desktop we require reportlab to be installed (pip install reportlab).
# - On Android, pyjnius must be available (python-for-android). Test on a real device.
# - You may need to request runtime permissions on Android 12+; the app calls request_android_permissions() best-effort.
#
# ESC/POS:
# - If your printer needs different commands (size/cut), adjust escpos_bytes_for_label().
# - If printing fails regularly, try increasing delay between jobs or splitting into single sends with small sleeps.
#
# Done.
