import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import time
import socket
import os

class ClawdLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("🦞 Clawdbot 启动控制台")
        self.root.geometry("600x550")
        
        # 进程对象存储
        self.proc_gateway = None
        self.proc_node = None
        
        # 状态标志
        self.gateway_running = False
        self.node_running = False

        # --- UI 布局 ---
        
        # 1. 控制区
        control_frame = tk.LabelFrame(root, text="服务选择与控制", padx=10, pady=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        # 复选框变量
        self.var_gateway = tk.BooleanVar(value=True)
        self.var_node = tk.BooleanVar(value=True)

        # Gateway 选项
        cb_gateway = tk.Checkbutton(control_frame, text="Gateway (大脑)", variable=self.var_gateway, font=("Microsoft YaHei", 10, "bold"))
        cb_gateway.grid(row=0, column=0, sticky="w", padx=20)
        
        self.lbl_gateway_status = tk.Label(control_frame, text="⚫ 未运行", fg="gray")
        self.lbl_gateway_status.grid(row=0, column=1, sticky="w")

        # Node 选项
        cb_node = tk.Checkbutton(control_frame, text="Node (手脚)", variable=self.var_node, font=("Microsoft YaHei", 10, "bold"))
        cb_node.grid(row=1, column=0, sticky="w", padx=20)
        
        self.lbl_node_status = tk.Label(control_frame, text="⚫ 未运行", fg="gray")
        self.lbl_node_status.grid(row=1, column=1, sticky="w")

        # 按钮区
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)
        
        self.btn_start = tk.Button(btn_frame, text="🚀 启动选中服务", bg="#e8f5e9", width=20, command=self.start_services)
        self.btn_start.pack(side="left", padx=10)
        
        self.btn_stop = tk.Button(btn_frame, text="🛑 停止所有服务", bg="#ffebee", width=20, command=self.stop_all)
        self.btn_stop.pack(side="left", padx=10)

        # 2. 日志区
        log_frame = tk.LabelFrame(root, text="运行日志", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=15, state='disabled', font=("Consolas", 9))
        self.log_area.pack(fill="both", expand=True)
        
        # 配置日志颜色
        self.log_area.tag_config('INFO', foreground='black')
        self.log_area.tag_config('GATEWAY', foreground='blue')
        self.log_area.tag_config('NODE', foreground='green')
        self.log_area.tag_config('ERROR', foreground='red')
        self.log_area.tag_config('SUCCESS', foreground='#2e7d32', font=("Consolas", 9, "bold"))

        # 3. 启动后台状态检测线程
        self.monitor_thread = threading.Thread(target=self.monitor_status, daemon=True)
        self.monitor_thread.start()

    def log(self, msg, tag='INFO'):
        """向日志区写入内容"""
        def _write():
            self.log_area.config(state='normal')
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.log_area.insert(tk.END, f"[{timestamp}] {msg}\n", tag)
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(0, _write)

    def is_port_open(self, port):
        """检测端口是否被占用（用于判断 Gateway 是否成功）"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', port)) == 0

    def run_command(self, cmd, tag, process_attr):
        """在线程中运行命令并实时读取输出"""
        try:
            # CREATE_NO_WINDOW 防止弹出黑框
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # 保存进程对象引用
            setattr(self, process_attr, process)
            self.log(f"正在启动 {tag}...", 'INFO')
            self.log(f"执行命令: {' '.join(cmd)}", 'INFO') # 打印具体执行的命令

            # 实时读取日志
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log(f"[{tag}] {line}", tag)
                    
                    # 针对 Node 的特殊检测
                    if tag == "NODE" and "Connected to gateway" in line:
                         self.log(">>> Node 已成功连接到大脑！ <<<", "SUCCESS")
                         self.node_running = True
                    # 针对 Gateway 的特殊检测 (Listening)
                    if tag == "GATEWAY" and "Listening" in line:
                         self.gateway_running = True
            
            self.log(f"{tag} 进程已退出。", 'ERROR')
            setattr(self, process_attr, None)
            
            if tag == "GATEWAY": self.gateway_running = False
            if tag == "NODE": self.node_running = False

        except Exception as e:
            self.log(f"启动 {tag} 失败: {str(e)}", 'ERROR')

    def start_services(self):
        # 1. 启动 Gateway
        if self.var_gateway.get():
            if self.is_port_open(18789):
                self.log("Gateway 端口(18789)已被占用，可能已经在运行中。", "ERROR")
                self.gateway_running = True
            else:
                # 【修改点】这里改成了 ["clawdbot", "gateway"]
                cmd_gateway = ["clawdbot", "gateway"]
                threading.Thread(target=self.run_command, args=(cmd_gateway, "GATEWAY", "proc_gateway"), daemon=True).start()
        
        # 2. 启动 Node (稍微延迟一点，等待 Gateway 初始化)
        if self.var_node.get():
            delay = 3 if self.var_gateway.get() else 0 # 稍微增加一点延时，给 Gateway 更多启动时间
            
            def start_node_delayed():
                time.sleep(delay)
                # Node 保持 run 模式，以便获取日志
                cmd_node = ["clawdbot", "node", "run", "--host", "127.0.0.1", "--port", "18789", "--display-name", "GuiNode"]
                self.run_command(cmd_node, "NODE", "proc_node")
            
            threading.Thread(target=start_node_delayed, daemon=True).start()

    def stop_all(self):
        self.log("正在停止所有服务...", "INFO")
        
        if self.proc_gateway:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc_gateway.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
        
        if self.proc_node:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc_node.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
            
        # 兜底清理
        subprocess.run(["taskkill", "/F", "/IM", "clawdbot.exe"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        subprocess.run(["taskkill", "/F", "/IM", "node.exe"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        
        self.gateway_running = False
        self.node_running = False
        self.log("所有服务已发送停止指令。", "INFO")

    def monitor_status(self):
        """后台线程：每秒刷新一次 UI 状态标签"""
        while True:
            # 检测 Gateway
            if self.is_port_open(18789):
                self.lbl_gateway_status.config(text="🟢 运行中 (端口监听)", fg="green")
                self.gateway_running = True
            else:
                self.lbl_gateway_status.config(text="⚫ 未运行", fg="gray")
                self.gateway_running = False
            
            # 检测 Node
            if self.proc_node and self.proc_node.poll() is None:
                if self.node_running: # 这个标志位由日志里的 "Connected" 触发
                    self.lbl_node_status.config(text="🟢 运行中 (已连接)", fg="green")
                else:
                    self.lbl_node_status.config(text="🟡 启动中...", fg="#fbc02d")
            else:
                self.lbl_node_status.config(text="⚫ 未运行", fg="gray")
                self.node_running = False
            
            time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = ClawdLauncher(root)
    def on_closing():
        app.stop_all()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()