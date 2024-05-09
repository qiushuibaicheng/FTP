import datetime
import json
import os.path
import threading
import gradio as gr
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler, ThrottledDTPHandler
from pyftpdlib.servers import FTPServer
# from pyftpdlib.log import LogFormatter
# import logging


class FTP:

    # 初始化
    def __init__(self):
        # 定义全局FTP服务器对象
        self.ftp_server = None
        # 当前用户列表
        self.username_list = None

    # 定义获取新用户ID的函数
    def get_new_user_id(self):
        current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{current_time}"

    # 定义启动FTP服务器的函数
    def start_ftp_server(self):
        try:
            # 初始化
            self.init_ftp_server()
            # 创建一个新线程用于运行FTP服务器
            server_thread = threading.Thread(target=self.ftp_server.serve_forever)
            # 启动线程
            server_thread.start()
            return "FTP服务器已启动"
        except Exception as e:
            return f"FTP服务器启动失败！！！{e}"

    # 定义停止FTP服务器的函数
    def stop_ftp_server(self):
        self.ftp_server.close_all()
        return "FTP服务器已停止"

    # 定义FTP服务器重启的函数
    def restart_ftp_server(self):
        # 停止FTP服务器
        self.stop_ftp_server()
        # 启动FTP服务器
        self.start_ftp_server()
        return "FTP服务器重启成功"

    # 定义添加用户的函数
    def add_ftp_user(self, username, password, permissions):
        if not self.username_list:
            self.add_users_config_file(username, password, permissions)
            return f"用户 {username} 已添加"
        if username in self.username_list:
            return f"用户 {username} 已存在，请重试"
        try:
            self.add_users_config_file(username, password, permissions)
            self.restart_ftp_server()
            return f"用户 {username} 已添加， 且服务器已重启"
        except Exception as e:
            return f"添加用户失败：{e}"

    # 在config.json中添加用户
    def add_users_config_file(self, username, password, permissions):
        with open("config.json", "r") as f:
            config = json.load(f)
        directory = os.path.join(config["root_directory"], username)
        new_id = self.get_new_user_id()
        config["users"][new_id] = {
            "username": username,
            "password": password,
            "directory": directory,
            "permissions": permissions
        }
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)

    # 初始化
    def init_ftp_server(self):

        self.username_list = []

        # 实例化虚拟用户，这是FTP的首要条件
        authorizer = DummyAuthorizer()

        # 读取config.json
        with open("config.json", "r") as f:
            config = json.load(f)

        if not os.path.exists(config["root_directory"]):
            os.mkdir(config["root_directory"])

        for _, user in config["users"].items():
            self.username_list.append(user["username"])
            if not os.path.exists(user["directory"]):
                os.mkdir(user["directory"])
            authorizer.add_user(user["username"], user["password"], user["directory"], perm=user["permissions"])

        # 初始化ftp句柄
        handler = FTPHandler
        handler.authorizer = authorizer

        # 添加被动端口范围
        handler.passive_ports = eval(config["passive_ports"])

        # 添加伪装地址
        # handler.masquerade_address = config["masquerade_address"]

        # 上传下载的速度设置
        dtp_handler = ThrottledDTPHandler
        dtp_handler.read_limit = config["read_limit"] * 1024  # read_limit kb/s
        dtp_handler.write_limit = config["write_limit"] * 1024  # write_limit kb/s
        handler.dtp_handler = dtp_handler

        # 监听ip和端口 ， linux里需要root用户才能使用21端口
        self.ftp_server = FTPServer((config["listen_ip"], config["listen_port"]), handler)

        # 最大连接数
        self.ftp_server.max_cons = config["max_cons"]
        self.ftp_server.max_cons_per_ip = config["max_cons_per_ip"]

    @staticmethod
    # 定义读取 JSON 配置的函数
    def load_config():
        with open("config.json", "r") as f:
            config = json.load(f)
        return "正在查看配置", config

    @staticmethod
    # 定义保存 JSON 配置的函数
    def save_config(config):
        keys = ['users', 'root_directory', 'passive_ports', 'read_limit', 'write_limit', 'listen_ip', 'listen_port',
                'max_cons', 'max_cons_per_ip', 'masquerade_address']
        for key in keys:
            if key not in config:
                return f"配置项 {key} 丢失"
        try:
            config = eval(config)
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            return f"配置失败{e}"
        return "配置已保存"


# 创建Gradio界面
with gr.Blocks() as admin_interface:
    gr.Markdown("### FTP服务器管理")

    ftp = FTP()

    with gr.Row():
        start_button = gr.Button("启动FTP服务器")
        stop_button = gr.Button("停止FTP服务器")

    server_status = gr.Textbox(label="服务器状态", interactive=False)

    start_button.click(ftp.start_ftp_server, outputs=server_status)
    stop_button.click(ftp.stop_ftp_server, outputs=server_status)

    gr.Markdown("### 添加FTP用户")
    with gr.Row():
        username_input = gr.Textbox(label="用户名")
        password_input = gr.Textbox(label="密码", type="password")
        permissions_input = gr.Textbox(label="权限", value="elradfmw")
        add_user_button = gr.Button("添加用户")

    add_user_button.click(ftp.add_ftp_user, inputs=[username_input, password_input, permissions_input],
                          outputs=server_status)

    with gr.Row():
        check_json = gr.Button("查看配置信息")
        submit_json = gr.Button("更新配置信息")

    save_status = gr.Textbox(label="保存状态", interactive=False)

    with gr.Row():
        json_data = gr.JSON(label="配置信息", value={})
        json_data_input = gr.Textbox(label="配置信息")
    check_json.click(FTP.load_config, outputs=[save_status, json_data])  # 加载配置
    submit_json.click(FTP.save_config, inputs=json_data_input, outputs=save_status)  # 保存配置

# 运行Gradio界面
admin_interface.launch()
