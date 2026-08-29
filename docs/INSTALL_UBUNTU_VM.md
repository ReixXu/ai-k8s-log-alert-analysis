# 在 VMware Workstation 创建 Linux 虚拟机（Ubuntu 22.04）

> 目标：创建 3 台可互通的 Ubuntu VM：master / worker1 / worker2。
> 后续所有 K8s 与 AIOps 操作都在这些 VM 上进行。

---

## 0. 前提

- VMware Workstation Pro（15/16/17 均可）已安装
- 下载 Ubuntu 22.04 LTS 镜像：server 版（无桌面、省资源）或 desktop 版
  - 建议 Server 版，运维更贴切。镜像：[ubuntu.com/download/server](https://ubuntu.com/download/server)
- 建议本机内存 ≥ 16G（3 台 VM 各 4~6G）

## 1. 网络规划（先定，避免返工）

使用 **NAT 模式**（简单、易互通），自动获取 IP，但为避免重启后变 IP，
建议在 VM 内绑定静态 IP。示例网段：`192.168.31.x`（NAT 网段以你本机为准，
可在 VMware「编辑 → 虚拟网络编辑器 → VMnet8」查看）。

| 角色 | 主机名 | 建议 IP |
|------|--------|---------|
| Master | master | 192.168.31.101 |
| Worker-1 | worker1 | 192.168.31.102 |
| Worker-2 | worker2 | 192.168.31.103 |

> ⚠️ 如果 NAT 网段不是你想要的，先在「虚拟网络编辑器」改 VMnet8 子网，再统一。

## 2. 创建第一台 VM（master）

1. VMware → 新建虚拟机 → 自定义（高级）
2. 选 ISO 镜像（Ubuntu server）
3. 分配资源：
   - 内存：≥ 4096MB（建议 6144）
   - CPU：≥ 2 核
   - 磁盘：≥ 40GB（建议 60GB，后续镜像多）
4. 网络：NAT
5. 安装系统时分盘时若提示"autoinstall 中断"，选手动或默认 LVM 即可
6. 设置用户：如 `ubuntu` / `ops`，密码简单便于本地实验

## 3. 配置静态 IP（master 示例）

Ubuntu 22.04 用 netplan。编辑 `/etc/netplan/00-installer-config.yaml`：

```yaml
network:
  version: 2
  ethernets:
    ens33:
      dhcp4: false
      addresses: [192.168.31.101/24]
      routes:
        - to: default
          via: 192.168.31.2   # 网关=NAT 的网关，VMnet8 里可查
      nameservers:
        addresses: [8.8.8.8, 223.5.5.5]
```

```bash
sudo netplan apply
ip a    # 验证 IP
# 注意 ens33 网卡名以实际为准 (ip link)
```

## 4. 克隆 worker1 / worker2（更快）

克隆会复制系统，用「链接克隆」省磁盘。但**克隆后需改主机名和 IP**：

```bash
sudo hostnamectl set-hostname worker1
sudo vi /etc/hosts          # 更新自身映射
# 再用步骤 3 把 IP 改成 102/103
```

> 若克隆导致网络异常，重装 netplan 配置或 `sudo rm /etc/machine-id; sudo systemd-machine-id-setup`。

## 5. 完成后的验证

```bash
# 三台都需要能 ping 通彼此主机名
ping master
ping worker1
ping worker2
```

确认互通后，进入 P1 阶段的 `init_node.sh` 初始化。

---

## 常见坑
- **网卡名不同**：`ip link` 查看，可能是 ens33 / ens161 / eth0。
- **克隆后 IP 冲突**：刚克隆时 eth0 会承接源机 IP，记得改。
- **swap 没关**：kubeadm 会报错，init_node.sh 已处理，但重启后靠 fstab 注释保证。
- **NAT DNS**：若内网 DNS 不通，nameservers 用 223.5.5.5 / 8.8.8.8。
