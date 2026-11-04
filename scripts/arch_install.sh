# 本文件是文档,不可运行
# 提供安装的办法

# connect wlan
# 需要 iwd
iwctl
[iwd]
device list
station "wlan0" scan
station "wlan0" get-networks
station "wlan0" connect "$SSID"

# 生成配置文件
wpa_passphrase "$SSID" "$pswd" > ./wifi.conf
# 连接网络
wpa_supplicant -c ./wifi.conf -i wlan0 &
# 自动获取IP
dhcpcd &




# ping test
ping archlinux.org

# time date setting
timedatectl set-ntp true
timedatectl
# disk
df -hT # all disk filesystem
lsblk # disk tree
fdisk -l
fdisk /dev/sda
# DOS(MBR) --> BIOS
# GPT -> UEFI
o
# new
n
# prime
p
e
# start
4096
# size
+512m
# print
p
# bootable
a
# Legacy BIOS(MBR)
# 1 swap  8G
# 2 /     32G bootable
# 3 /home +

cfdisk

# format EFI
mkfs.fat -F32 /dev/nvme0n1p1
mkfs.btrfs -f /dev/nvme0n1p3   # -f 强制覆盖

# mount
# /
mount -t btrfs /dev/nvme0n1p2 /mnt
# boot efi
mkdir /mnt/boot
mount /dev/nvme0n1p1 /mnt/boot

lsblk
# install os
vim /etc/pacman.d/mirrorlist

"Server = https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch"

# download & install
pacstrap -K /mnt base linux linux-firmware vim sudo grub dhcpcd iwd
# fstab
genfstab -U /mnt > /mnt/etc/fstab
# change root new os
arch-chroot /mnt

# localtime set
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/locale.gen
hwclock --systohc
# locale language
vim /etc/locale.gen
"en_US.UTF-8 UTF-8"
"zh_CN.UTF-8 UTF-8"
locale-gen

vim /etc/locale.conf
LANG=en_GB.UTF-8
# hostname
vim /etc/hostname
"tempest"

# root password
passwd

# GRUB
pacman -S grub dosfstools os-prober mtools efibootmgr
grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB
grub-install --target=i386-pc /dev/sdb
grub-mkconfig -o /boot/grub/grub.cfg

# reboot
exit
umount -R /mnt
poweroff
# new os
# create user


# GUI sway
sudo pacman -S mesa vulkan-intel intel-media-driver
sudo pacman -S sway swayidle swaylock waybar wofi alacritty
mkdir -p ~/.config/sway
cp /etc/sway/config ~/.config/sway/
sudo tee /etc/modprobe.d/blacklist-nouveau.conf > /dev/null <<EOF
blacklist nouveau
options nouveau modeset=0
EOF
sudo mkinitcpio -P
if [ -z $DISPLAY ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec sway
fi
# font
fc-list

# NVIDIA 有待验证
sudo pacman -S nvidia nvidia-utils nvidia-settings lib32-nvidia-utils

### 安装之后
# `Paru` AUR包管理器
sudo pacman -S --needed base-devel
git clone https://aur.archlinux.org/paru.git
cd paru
makepkg -si
# minecraft

java-xx-openjdk
java-xx-openjdk-headless

systemctl enable iwd
# 加入 wheel, 可 sudo
usermod -aG wheel [username]
grep -n wheel /etc/sudoers

# 在 tty 中使用汉语 kmscon
sudo pacman -S kmscon noto-fonts-cjk
# 编辑配置
nvim /etc/kmscon/kmscon.conf

"""
font-name=Noto Sans CJK SC
font-size=16
xkb-layout=us
"""
# 禁用指定 tty
sudo systemctl disable getty@tty2.service
# 接管该 tty
sudo systemctl enable --now kmsconvt@tty2.service




