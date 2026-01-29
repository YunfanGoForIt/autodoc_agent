# Syncthing 用户级安装配置

## 环境
- 用户：yunfan
- 安装目录：`~/syncthing/`
- 同步目录：`~/syncthing/podcast_notes/`

## 安装步骤

### 1. 下载 Syncthing

```bash
mkdir -p ~/syncthing
cd ~/syncthing
wget https://github.com/syncthing/syncthing/releases/download/v1.29.0/syncthing-linux-amd64-v1.29.0.tar.gz
tar xzf syncthing-linux-amd64-v1.29.0.tar.gz
```

### 2. 创建同步目录

```bash
mkdir -p ~/syncthing/podcast_notes
mkdir -p ~/.config/syncthing
```

### 3. 创建 systemd 用户服务

文件路径：`~/.config/systemd/user/syncthing.service`

```ini
[Unit]
Description=Syncthing

[Service]
ExecStart=/home/yunfan/syncthing/syncthing-linux-amd64-v1.29.0/syncthing
Restart=on-failure

[Install]
WantedBy=default.target
```

### 4. 启用并启动服务

```bash
systemctl --user daemon-reload
systemctl --user enable syncthing.service
systemctl --user start syncthing.service
```

## 常用命令

| 操作 | 命令 |
|------|------|
| 启动服务 | `systemctl --user start syncthing.service` |
| 停止服务 | `systemctl --user stop syncthing.service` |
| 查看状态 | `systemctl --user status syncthing.service` |
| 查看日志 | `journalctl --user -u syncthing.service -f` |
| 重启服务 | `systemctl --user restart syncthing.service` |

## 坑点记录

### 1. 新版本参数变化
- v1.29.0 已移除 `-no-browser` 参数
- `-home` 参数简化为直接使用

错误示例：
```bash
syncthing -no-browser -home=/path/to/config  # 报错: unknown flag -n
```

正确示例：
```bash
syncthing  # 直接运行即可
```

### 2. 用户级服务
- 使用 `systemctl --user` 而非 `systemctl`
- 服务文件放在 `~/.config/systemd/user/`
- 不需要 root 权限

### 3. 端口冲突
- 如果启动失败，检查是否有其他实例在运行：
  ```bash
  pkill -9 syncthing
  ```
- Syncthing 默认使用 8384 端口

## 配置 Syncthing GUI

访问 http://localhost:8384

1. 添加同步文件夹：
   - 路径：`/home/yunfan/syncthing/podcast_notes`
   - 文件夹 ID：`podcast_notes`
   - 设置共享密码

2. 其他设备同步：
   - 安装 Syncthing
   - 使用相同的「文件夹 ID」添加同步文件夹
