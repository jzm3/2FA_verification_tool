import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyotp
import time
import base64
import qrcode
from PIL import Image, ImageTk
import os

class TwoFactorAuthApp:
    def __init__(self, root):
        self.root = root
        self.root.title("2FA 验证工具")
        self.root.geometry("500x600")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f2f5")
        
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#f0f2f5")
        self.style.configure("TLabel", background="#f0f2f5", font=("Arial", 10))
        self.style.configure("TButton", font=("Arial", 10), padding=6)
        self.style.configure("Header.TLabel", font=("Arial", 16, "bold"), foreground="#2c3e50")
        self.style.configure("Code.TLabel", font=("Courier", 24, "bold"), foreground="#3498db")
        self.style.configure("Progress.Horizontal.TProgressbar", background="#3498db")

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
        
        self.tab_control.pack(expand=1, fill="both")

        self.init_generate_tab()

        self.init_key_tab()

        self.totp = None
        self.current_code = ""
        self.is_valid_key = False

        self.code_label.configure(text="------")
        self.time_remaining.set(30)
        self.status_label.configure(text="请输入2FA密钥并点击生成")

        self.update_timer()

        self.key_entry.focus_set()
        self.key_entry.config(style="Active.TEntry")
    
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

        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1*(event.delta/120)), "units"))

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
        except Exception as e:
            messagebox.showerror("错误", f"保存密钥时出错: {str(e)}")
    
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

if __name__ == "__main__":
    root = tk.Tk()
    app = TwoFactorAuthApp(root)
    root.mainloop()