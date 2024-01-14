#!/bin/bash
sudo apt update
sudo apt install -y vim git net-tools wget gcc iperf3 p7zip-full libpcre3 libpcre3-dev zlib1g zlib1g-dev screen htop iftop iotop mosh curl make unzip python3 python3-pip libssl-dev

python3 -m pip install numpy

# https://github.com/nodesource/distributions#debinstall
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 
sudo apt update
sudo apt install -y nodejs

sudo apt install -y zsh percol
sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

sed -i 's/ZSH_THEME=".*"/ZSH_THEME="dpoggi"/g' ~/.zshrc
sed -i 's/plugins=(.*)/plugins=(git percol)/g' ~/.zshrc

# install after zsh
# curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
