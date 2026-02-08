# 1. 获取 WSL 的最新 IP
$wsl_ip = (wsl hostname -I).Trim()
Write-Host "WSL IP found: $wsl_ip"

# 2. 删除旧转发规则
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0

# 3. 添加新规则
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wsl_ip

Write-Host "端口转发已更新：所有访问本机 8000 的请求都会转发给 WSL ($wsl_ip:8000)"