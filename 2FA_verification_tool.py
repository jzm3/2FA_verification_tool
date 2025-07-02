import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import pyotp
import time
import base64
import qrcode
from PIL import Image, ImageTk
import os
import json
from cryptography.fernet import Fernet
import hashlib
import sys
import threading
import platform
import subprocess


class TwoFactorAuthApp:
    def __init__(self, root, auto_import_file=None):
        self.root = root
        self.root.title("2FA 验证工具")
        self.root.geometry("500x600")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f2f5")

        self.auto_import_file = auto_import_file

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#f0f2f5")
        self.style.configure("TLabel", background="#f0f2f5", font=("Arial", 10))
        self.style.configure("TButton", font=("Arial", 10), padding=6)
        self.style.configure("Header.TLabel", font=("Arial", 16, "bold"), foreground="#2c3e50")
        self.style.configure("Code.TLabel", font=("Courier", 24, "bold"), foreground="#3498db")
        self.style.configure("Progress.Horizontal.TProgressbar", background="#3498db")
        self.style.configure("Key.TButton", font=("Arial", 9), padding=3)

        self.style.configure("Active.TEntry", fieldbackground="#ffffff",
                             highlightthickness=2, highlightbackground="#3498db",
                             highlightcolor="#3498db")
        self.style.configure("Normal.TEntry", fieldbackground="#ffffff",
                             highlightthickness=1, highlightbackground="#bdc3c7",
                             highlightcolor="#bdc3c7")

        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.title_label = ttk.Label(self.main_frame, text="2FA 验证工具", style="Header.TLabel")
        self.title_label.pack(pady=(0, 20))

        self.tab_control = ttk.Notebook(self.main_frame)

        self.generate_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.generate_tab, text="生成验证码")

        self.key_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.key_tab, text="密钥管理")

        self.vault_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.vault_tab, text="密钥库")

        self.tab_control.pack(expand=1, fill="both")

        self.init_generate_tab()

        self.init_key_tab()

        self.init_vault_tab()

        self.totp = None
        self.current_code = ""
        self.is_valid_key = False
        self.used_keys = {}
        self.current_vault_file = None
        self.vault_data = None

        self.code_label.configure(text="------")
        self.time_remaining = tk.IntVar(value=30)
        self.status_label.configure(text="请输入2FA密钥并点击生成")

        self.update_timer()

        self.key_entry.focus_set()
        self.key_entry.config(style="Active.TEntry")

        self.tab_control.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        if self.auto_import_file:
            self.root.after(500, self.auto_import_vault)

    def auto_import_vault(self):
        if not os.path.exists(self.auto_import_file):
            messagebox.showerror("错误", f"文件不存在: {self.auto_import_file}")
            return

        self.tab_control.select(2)

        self.root.after(100, lambda: self.import_vault_from_file(self.auto_import_file))

    def import_vault_from_file(self, file_path):
        username = simpledialog.askstring("用户名", "请输入密钥库的用户名:", parent=self.root)
        if not username:
            return

        password = simpledialog.askstring("密码", "请输入密钥库的密码:", parent=self.root, show="*")
        if not password:
            return

        try:
            with open(file_path, "rb") as f:
                data = f.read()

            salt = data[:16]
            encrypted_data = data[16:]

            kdf = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt,
                100000,
                dklen=32
            )

            fernet_key = base64.urlsafe_b64encode(kdf)
            fernet = Fernet(fernet_key)

            decrypted_data = fernet.decrypt(encrypted_data)
            vault_data = json.loads(decrypted_data.decode())

            if vault_data.get("username") != username:
                messagebox.showerror("验证失败", "用户名或密码不正确")
                return

            self.current_vault_file = file_path
            self.vault_data = vault_data

            self.switch_vault_btn.pack(side=tk.LEFT, padx=5)

            self.load_vault_keys()

            messagebox.showinfo("成功", "密钥库已成功导入")
        except Exception as e:
            messagebox.showerror("导入错误", f"导入密钥库时出错: {str(e)}")

    def on_tab_changed(self, event):
        current_tab = self.tab_control.index(self.tab_control.select())

        if current_tab == 2 and self.current_vault_file:
            self.load_vault_keys()

    def init_generate_tab(self):
        key_frame = ttk.Frame(self.generate_tab)
        key_frame.pack(fill=tk.X, padx=10, pady=10)

        key_label = ttk.Label(key_frame, text="输入密钥:")
        key_label.pack(side=tk.LEFT, padx=(0, 10))

        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(
            key_frame,
            textvariable=self.key_var,
            width=40,
            style="Active.TEntry"
        )
        self.key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

        self.key_entry.bind("<FocusIn>", lambda e: self.entry_focus_in(self.key_entry))
        self.key_entry.bind("<FocusOut>", lambda e: self.entry_focus_out(self.key_entry))

        self.key_entry.bind("<Return>", self.update_code)

        generate_btn = ttk.Button(key_frame, text="生成验证码", command=self.update_code)
        generate_btn.pack(side=tk.LEFT)

        code_frame = ttk.Frame(self.generate_tab)
        code_frame.pack(fill=tk.X, padx=10, pady=20)

        self.code_label = ttk.Label(code_frame, text="------", style="Code.TLabel")
        self.code_label.pack(pady=20)

        self.time_remaining = tk.IntVar(value=30)
        self.progress_bar = ttk.Progressbar(
            code_frame,
            orient="horizontal",
            length=300,
            mode="determinate",
            variable=self.time_remaining,
            maximum=30,
            style="Progress.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(pady=10)

        self.status_label = ttk.Label(code_frame, text="请输入2FA密钥并点击生成")
        self.status_label.pack(pady=5)

        separator = ttk.Separator(self.generate_tab, orient="horizontal")
        separator.pack(fill=tk.X, padx=10, pady=20)

        instructions = ttk.Frame(self.generate_tab)
        instructions.pack(fill=tk.X, padx=10, pady=10)

        instructions_text = (
            "使用说明:\n"
            "1. 在输入框中输入您的2FA密钥\n"
            "2. 点击'生成验证码'按钮或按Enter键\n"
            "3. 使用生成的6位验证码登录您的账户\n"
            "4. 验证码每30秒自动刷新一次"
        )
        instructions_label = ttk.Label(instructions, text=instructions_text, justify=tk.LEFT)
        instructions_label.pack(anchor=tk.W)

    def init_key_tab(self):
        canvas = tk.Canvas(self.key_tab, borderwidth=0, highlightthickness=0, bg="#f0f2f5")
        scrollbar = ttk.Scrollbar(self.key_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set, bg="#f0f2f5")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        generate_frame = ttk.Frame(scrollable_frame)
        generate_frame.pack(fill=tk.X, padx=10, pady=10, anchor="nw")

        generate_label = ttk.Label(generate_frame, text="生成新密钥:")
        generate_label.pack(side=tk.LEFT, padx=(0, 10))

        self.new_key_var = tk.StringVar()
        new_key_entry = ttk.Entry(
            generate_frame,
            textvariable=self.new_key_var,
            width=30,
            state="readonly",
            style="Normal.TEntry"
        )
        new_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

        new_key_entry.bind("<FocusIn>", lambda e: self.entry_focus_in(new_key_entry))
        new_key_entry.bind("<FocusOut>", lambda e: self.entry_focus_out(new_key_entry))

        generate_btn = ttk.Button(generate_frame, text="生成", command=self.generate_key)
        generate_btn.pack(side=tk.LEFT)

        qr_frame = ttk.Frame(scrollable_frame)
        qr_frame.pack(fill=tk.X, padx=10, pady=20, anchor="nw")

        self.qr_label = ttk.Label(qr_frame)
        self.qr_label.pack()

        qr_tip = ttk.Label(qr_frame, text="使用认证应用扫描此二维码添加密钥", foreground="#7f8c8d")
        qr_tip.pack(pady=(5, 0))

        separator = ttk.Separator(scrollable_frame, orient="horizontal")
        separator.pack(fill=tk.X, padx=10, pady=20, anchor="nw")

        save_frame = ttk.Frame(scrollable_frame)
        save_frame.pack(fill=tk.X, padx=10, pady=10, anchor="nw")

        save_label = ttk.Label(save_frame, text="保存密钥:")
        save_label.pack(side=tk.LEFT, padx=(0, 10))

        self.save_key_var = tk.StringVar()
        save_key_entry = ttk.Entry(
            save_frame,
            textvariable=self.save_key_var,
            width=30,
            style="Normal.TEntry"
        )
        save_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))

        save_key_entry.bind("<FocusIn>", lambda e: self.entry_focus_in(save_key_entry))
        save_key_entry.bind("<FocusOut>", lambda e: self.entry_focus_out(save_key_entry))

        save_btn = ttk.Button(save_frame, text="保存到文件", command=self.save_key)
        save_btn.pack(side=tk.LEFT)

        instructions = ttk.Frame(scrollable_frame)
        instructions.pack(fill=tk.X, padx=10, pady=10, anchor="nw")

        instructions_text = (
            "使用说明:\n"
            "1. 点击'生成'按钮创建新的2FA密钥\n"
            "2. 使用手机认证应用扫描二维码添加密钥\n"
            "3. 保存密钥到安全的地方以备后用\n"
            "4. 在'生成验证码'标签页中使用密钥"
        )
        instructions_label = ttk.Label(instructions, text=instructions_text, justify=tk.LEFT)
        instructions_label.pack(anchor=tk.W)

        security_frame = ttk.Frame(scrollable_frame)
        security_frame.pack(fill=tk.X, padx=10, pady=10, anchor="nw")

        security_text = (
            "安全提示:\n"
            "• 密钥是访问您账户的关键，请妥善保管\n"
            "• 不要与他人分享您的密钥\n"
            "• 建议将密钥保存在加密的密码管理器中"
        )
        security_label = ttk.Label(security_frame, text=security_text, justify=tk.LEFT, foreground="#c0392b")
        security_label.pack(anchor=tk.W)

    def init_vault_tab(self):
        canvas = tk.Canvas(self.vault_tab, borderwidth=0, highlightthickness=0, bg="#f0f2f5")
        scrollbar = ttk.Scrollbar(self.vault_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set, bg="#f0f2f5")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        btn_frame = ttk.Frame(scrollable_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        export_btn = ttk.Button(
            btn_frame,
            text="导出密钥库",
            command=self.export_vault,
            width=15
        )
        export_btn.pack(side=tk.LEFT, padx=5)

        import_btn = ttk.Button(
            btn_frame,
            text="导入密钥库",
            command=self.import_vault,
            width=15
        )
        import_btn.pack(side=tk.LEFT, padx=5)

        self.switch_vault_btn = ttk.Button(
            btn_frame,
            text="切换数据文件",
            command=self.switch_vault,
            width=15
        )

        self.switch_vault_btn.pack_forget()

        if platform.system() == "Windows":
            file_assoc_frame = ttk.Frame(scrollable_frame)
            file_assoc_frame.pack(fill=tk.X, padx=10, pady=10)

            file_assoc_label = ttk.Label(file_assoc_frame, text="文件关联:", font=("Arial", 9, "bold"))
            file_assoc_label.pack(side=tk.LEFT, padx=(0, 5))

            set_assoc_btn = ttk.Button(
                file_assoc_frame,
                text="设置关联",
                command=self.set_file_association,
                width=10
            )
            set_assoc_btn.pack(side=tk.LEFT, padx=2)

            remove_assoc_btn = ttk.Button(
                file_assoc_frame,
                text="移除关联",
                command=self.remove_file_association,
                width=10
            )
            remove_assoc_btn.pack(side=tk.LEFT, padx=2)

            info_icon = ttk.Label(file_assoc_frame, text="ⓘ", foreground="#3498db", cursor="hand2")
            info_icon.pack(side=tk.LEFT, padx=(10, 0))
            info_icon.bind("<Button-1>", lambda e: messagebox.showinfo(
                "文件关联帮助",
                "设置文件关联后，双击.2favault文件将自动启动程序并导入密钥库。\n\n"
                "此功能仅适用于Windows系统。"
            ))

        info_frame = ttk.Frame(scrollable_frame)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        info_text = (
            "密钥库功能允许您安全地保存和管理所有2FA密钥。\n\n"
            "导出功能：\n"
            "• 将您使用过的所有密钥加密保存到文件\n"
            "• 需要设置用户名和密码进行保护\n"
            "• 为每个密钥指定一个名称以便识别\n\n"
            "导入功能：\n"
            "• 从加密文件加载密钥库\n"
            "• 需要输入正确的用户名和密码\n"
            "• 点击密钥可自动复制并生成验证码"
        )
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
        info_label.pack(anchor=tk.W)

        security_frame = ttk.Frame(scrollable_frame)
        security_frame.pack(fill=tk.X, padx=10, pady=10)

        security_text = (
            "安全提示:\n"
            "• 密钥是访问您账户的关键，请妥善保管\n"
            "• 不要与他人分享您的密钥\n"
            "• 建议将密钥保存在加密的密码管理器中"
        )
        security_label = ttk.Label(security_frame, text=security_text, justify=tk.LEFT, foreground="#c0392b")
        security_label.pack(anchor=tk.W)

        separator = ttk.Separator(scrollable_frame, orient="horizontal")
        separator.pack(fill=tk.X, padx=10, pady=10)

        self.keys_frame = ttk.Frame(scrollable_frame)
        self.keys_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.vault_status = ttk.Label(
            self.keys_frame,
            text="请导入密钥库以查看保存的密钥",
            font=("Arial", 10, "italic"),
            foreground="#7f8c8d"
        )
        self.vault_status.pack(pady=50)

    def set_file_association(self):
        try:
            if getattr(sys, 'frozen', False):
                app_path = sys.executable
            else:
                app_path = os.path.abspath(sys.argv[0])

            reg_script = f"""
            Windows Registry Editor Version 5.00

            [HKEY_CLASSES_ROOT\\.2favault]
            @="2FAVaultFile"

            [HKEY_CLASSES_ROOT\\2FAVaultFile]
            @="2FA 密钥库文件"

            [HKEY_CLASSES_ROOT\\2FAVaultFile\\DefaultIcon]
            @="\\"{app_path}\\""

            [HKEY_CLASSES_ROOT\\2FAVaultFile\\shell]
            @="open"

            [HKEY_CLASSES_ROOT\\2FAVaultFile\\shell\\open]
            @="打开"

            [HKEY_CLASSES_ROOT\\2FAVaultFile\\shell\\open\\command]
            @="\\"{app_path}\\" \\\"%1\\\"" 
            """

            reg_path = os.path.join(os.getenv('TEMP'), '2fa_file_assoc.reg')
            with open(reg_path, 'w') as f:
                f.write(reg_script)

            subprocess.run(f'regedit /s "{reg_path}"', shell=True)
            os.remove(reg_path)

            messagebox.showinfo("成功", "文件关联设置成功！\n现在可以双击.2favault文件自动导入。")
        except Exception as e:
            messagebox.showerror("错误", f"设置文件关联时出错: {str(e)}")

    def remove_file_association(self):
        try:
            reg_script = """
            Windows Registry Editor Version 5.00

            [-HKEY_CLASSES_ROOT\\.2favault]
            [-HKEY_CLASSES_ROOT\\2FAVaultFile]
            """

            reg_path = os.path.join(os.getenv('TEMP'), '2fa_remove_assoc.reg')
            with open(reg_path, 'w') as f:
                f.write(reg_script)

            subprocess.run(f'regedit /s "{reg_path}"', shell=True)
            os.remove(reg_path)

            messagebox.showinfo("成功", "文件关联已移除！")
        except Exception as e:
            messagebox.showerror("错误", f"移除文件关联时出错: {str(e)}")

    def load_vault_keys(self):
        for widget in self.keys_frame.winfo_children():
            widget.destroy()

        if not self.current_vault_file or not self.vault_data:
            self.vault_status = ttk.Label(
                self.keys_frame,
                text="没有可用的密钥数据",
                font=("Arial", 10, "italic"),
                foreground="#7f8c8d"
            )
            self.vault_status.pack(pady=50)
            return

        container = ttk.Frame(self.keys_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0, bg="#f0f2f5")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set, bg="#f0f2f5")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        file_label = ttk.Label(
            scrollable_frame,
            text=f"当前密钥库: {os.path.basename(self.current_vault_file)}",
            font=("Arial", 10, "bold"),
            foreground="#3498db"
        )
        file_label.pack(pady=(0, 10), anchor=tk.W, padx=5)

        for key_name, key_value in self.vault_data["keys"].items():
            key_frame = ttk.Frame(scrollable_frame, padding=5)
            key_frame.pack(fill=tk.X, pady=2, padx=5)

            name_label = ttk.Label(
                key_frame,
                text=f"{key_name}:",
                font=("Arial", 9, "bold"),
                width=25,
                anchor=tk.W
            )
            name_label.pack(side=tk.LEFT, padx=(0, 5))

            truncated_key = key_value[:4] + "****" + key_value[-4:]
            key_label = ttk.Label(
                key_frame,
                text=truncated_key,
                font=("Courier", 9),
                foreground="#7f8c8d"
            )
            key_label.pack(side=tk.LEFT, padx=(0, 5), expand=True, fill=tk.X)

            use_btn = ttk.Button(
                key_frame,
                text="使用密钥",
                style="Key.TButton",
                command=lambda k=key_value: self.use_vault_key(k)
            )
            use_btn.pack(side=tk.RIGHT)

    def use_vault_key(self, key_value):
        self.root.clipboard_clear()
        self.root.clipboard_append(key_value)

        self.key_var.set(key_value)

        self.tab_control.select(0)

        self.update_code()

        messagebox.showinfo("成功", "密钥已复制并自动填入输入框，验证码已生成")

        self.add_used_key("从密钥库导入", key_value)

    def export_vault(self):
        if not self.used_keys:
            messagebox.showinfo("提示", "尚未使用任何密钥，无法导出密钥库")
            return

        username = simpledialog.askstring("用户名", "请输入用于保护密钥库的用户名:", parent=self.root)
        if not username:
            return

        password = simpledialog.askstring("密码", "请输入用于加密密钥库的密码:", parent=self.root, show="*")
        if not password:
            return

        key_data = {}
        for key_name, key_value in self.used_keys.items():
            name = simpledialog.askstring(
                "密钥命名",
                f"请为密钥 '{key_value[:4]}****{key_value[-4:]}' 指定一个名称:",
                parent=self.root,
                initialvalue=key_name
            )
            if not name:
                name = key_name
            key_data[name] = key_value

        vault_data = {
            "username": username,
            "keys": key_data
        }

        try:
            salt = os.urandom(16)
            kdf = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt,
                100000,
                dklen=32
            )

            fernet_key = base64.urlsafe_b64encode(kdf)
            fernet = Fernet(fernet_key)

            encrypted_data = fernet.encrypt(json.dumps(vault_data).encode())

            final_data = salt + encrypted_data
        except Exception as e:
            messagebox.showerror("加密错误", f"加密数据时出错: {str(e)}")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".2favault",
            filetypes=[("2FA 密钥库", "*.2favault"), ("所有文件", "*.*")],
            title="保存密钥库",
            initialfile="my_2fa_vault.2favault"
        )

        if not file_path:
            return

        try:
            with open(file_path, "wb") as f:
                f.write(final_data)
            messagebox.showinfo("成功", f"密钥库已成功保存到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存密钥库时出错: {str(e)}")

    def import_vault(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("2FA 密钥库", "*.2favault"), ("所有文件", "*.*")],
            title="选择密钥库文件"
        )

        if not file_path:
            return

        self.import_vault_from_file(file_path)

    def switch_vault(self):
        self.current_vault_file = None
        self.vault_data = None

        self.switch_vault_btn.pack_forget()

        self.import_vault()

    def entry_focus_in(self, entry_widget):
        entry_widget.config(style="Active.TEntry")

        if entry_widget.cget("state") == "readonly":
            entry_widget.after(10, lambda: entry_widget.selection_range(0, tk.END))

    def entry_focus_out(self, entry_widget):
        entry_widget.config(style="Normal.TEntry")

    def generate_key(self):
        key = base64.b32encode(os.urandom(10)).decode('utf-8')
        self.new_key_var.set(key)
        self.save_key_var.set(key)

        self.generate_qr_code(key)

        self.add_used_key(f"新密钥_{len(self.used_keys) + 1}", key)

    def generate_qr_code(self, key):
        totp_uri = pyotp.TOTP(key).provisioning_uri(name="MyApp", issuer_name="2FA Tool")

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=6,
            border=2,
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        tk_img = ImageTk.PhotoImage(img)
        self.qr_label.configure(image=tk_img)
        self.qr_label.image = tk_img

    def save_key(self):
        key = self.save_key_var.get()
        if not key:
            messagebox.showwarning("警告", "请输入要保存的密钥")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="保存2FA密钥",
            initialfile="2fa_key.txt"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w") as f:
                f.write(f"2FA密钥: {key}\n")
                f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n安全提示:\n")
                f.write("- 这是您的重要身份验证密钥\n")
                f.write("- 请不要与他人分享此密钥\n")
                f.write("- 建议将此文件保存在安全的位置\n")

            messagebox.showinfo("成功", f"密钥已保存到:\n{file_path}")

            self.add_used_key(f"已保存密钥_{len(self.used_keys) + 1}", key)
        except Exception as e:
            messagebox.showerror("错误", f"保存密钥时出错: {str(e)}")

    def add_used_key(self, name, key):
        for existing_key in self.used_keys.values():
            if existing_key == key:
                return

        self.used_keys[name] = key

    def update_code(self, event=None):
        key = self.key_var.get().strip().replace(" ", "").upper()

        if not key:
            self.is_valid_key = False
            self.totp = None
            self.code_label.configure(text="------")
            self.time_remaining.set(30)
            self.status_label.configure(text="请输入2FA密钥并点击生成")
            return

        try:
            self.totp = pyotp.TOTP(key)
            self.current_code = self.totp.now()
            self.code_label.configure(text=self.current_code)
            self.time_remaining.set(30)
            self.status_label.configure(text="验证码生成成功")
            self.is_valid_key = True

            self.add_used_key(f"已验证密钥_{len(self.used_keys) + 1}", key)
        except Exception as e:
            messagebox.showerror("错误", f"无效的密钥格式: {str(e)}")
            self.code_label.configure(text="------")
            self.time_remaining.set(30)
            self.status_label.configure(text="无效密钥，请重新输入")
            self.is_valid_key = False
            self.totp = None

    def update_timer(self):
        if self.totp and self.is_valid_key:
            remaining = 30 - int(time.time()) % 30

            if remaining == 30:
                self.current_code = self.totp.now()
                self.code_label.configure(text=self.current_code)

            self.time_remaining.set(remaining)
            self.status_label.configure(text=f"验证码将在 {remaining} 秒后刷新")
        else:
            if self.time_remaining.get() != 30:
                self.time_remaining.set(30)

            if "无效" not in self.status_label.cget("text"):
                self.status_label.configure(text="请输入2FA密钥并点击生成")

        self.root.after(500, self.update_timer)


def main():
    auto_import_file = None
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path) and file_path.endswith('.2favault'):
            auto_import_file = file_path

    root = tk.Tk()
    app = TwoFactorAuthApp(root, auto_import_file)
    root.mainloop()


if __name__ == "__main__":
    main()