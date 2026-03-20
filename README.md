# QQ Map CLI

一个基于腾讯位置服务 WebService API 的命令行工具，支持：

- 地址转经纬度
- 两个地址名之间距离与时长查询
- 坐标距离矩阵查询
- 首次运行自动生成配置文件
- 打包为可直接分发的 macOS / Windows / Linux 可执行文件

## 功能概览

当前 CLI 提供这些子命令：

- `setup`
  用于初始化或更新当前工作目录下的 `qq_map_cli_config.json`
- `geocoder`
  地址转经纬度，返回结构化行政区划信息
- `distance-matrix`
  基于坐标做一对一、一对多、多对多距离查询
- `address-distance`
  输入两个地址名，内部自动调用 `geocoder + distance-matrix`

主入口脚本是 `qq_map_cli.py`。

## 给最终用户的使用方式

如果你已经从发布页面下载好了打包产物：

- macOS 用户下载 `qq-map-cli-darwin-*.zip`
- Windows 用户下载 `qq-map-cli-windows-*.zip`
- Linux 用户下载 `qq-map-cli-linux-*.zip`

解压后可直接运行。

### macOS 用户

第一次初始化配置：

```bash
./qq-map-cli setup --key "你的腾讯地图 key"
```

查询两个地址之间的驾车距离：

```bash
./qq-map-cli address-distance \
  --from-address "北京市海淀区中关村大街27号" \
  --to-address "北京市朝阳区望京街10号" \
  --mode driving
```

### Windows 用户

第一次初始化配置：

```powershell
.\qq-map-cli.exe setup --key "你的腾讯地图 key"
```

查询两个地址之间的驾车距离：

```powershell
.\qq-map-cli.exe address-distance `
  --from-address "北京市海淀区中关村大街27号" `
  --to-address "北京市朝阳区望京街10号" `
  --mode driving
```

### Linux 用户

第一次初始化配置：

```bash
./qq-map-cli setup --key "你的腾讯地图 key"
```

查询两个地址之间的驾车距离：

```bash
./qq-map-cli address-distance \
  --from-address "北京市海淀区中关村大街27号" \
  --to-address "北京市朝阳区望京街10号" \
  --mode driving
```

### 如果暂时没有 key

可以先执行：

```bash
./qq-map-cli setup
```

或者 Windows：

```powershell
.\qq-map-cli.exe setup
```

这会在当前目录生成一个 `qq_map_cli_config.json`，之后把 `key` 填进去即可。

## 从源码运行

如果不打包，直接运行 Python 脚本也可以：

```bash
python3 qq_map_cli.py setup --key "你的腾讯地图 key"
python3 qq_map_cli.py geocoder --address "北京市海淀区彩和坊路海淀西大街74号"
python3 qq_map_cli.py address-distance --from-address "A" --to-address "B"
```

## 本地打包

### 先安装构建依赖

```bash
python3 -m pip install -r requirements-build.txt
```

Windows 也一样：

```powershell
python -m pip install -r requirements-build.txt
```

### macOS / Linux 本地打包

```bash
python3 scripts/build_release.py
```

生成结果：

- `dist/`
  原始可执行文件
- `artifacts/`
  可直接分发的 zip 包

### Windows 本地打包

你可以直接运行 Python 版构建脚本：

```powershell
python scripts/build_release.py
```

也可以使用仓库里准备好的 Windows 包装脚本：

```powershell
.\scripts\build_release.ps1
```

或者：

```cmd
scripts\build_release.bat
```

### 可选参数

- `--onedir`
  打包成目录形式，而不是单文件
- `--no-clean`
  保留上一次的 `build/` 和 `dist/`

示例：

```bash
python3 scripts/build_release.py --onedir
```

## GitHub Actions 自动打包与发布

仓库已经包含工作流：`.github/workflows/build-release.yml`

行为如下：

- 手动触发 workflow 时：
  构建 macOS、Windows、Linux 三个平台的 zip，并作为 Actions artifacts 上传
- 推送 tag，且 tag 名匹配 `v*` 时：
  构建 macOS、Windows、Linux 包
  然后自动发布到 GitHub Release

### 推荐发布流程

1. 提交代码
2. 打 tag，例如：

```bash
git tag v1.0.0
git push origin v1.0.0
```

3. 等待 GitHub Actions 完成
4. 在 GitHub Releases 页面直接拿到：
   - macOS zip
   - Windows zip
   - Linux zip

这样最终用户不需要装 Python，也不需要自己构建。

## 配置文件说明

默认配置文件名：

```text
qq_map_cli_config.json
```

默认内容：

```json
{
  "key": "你的腾讯地图 key"
}
```

CLI 读取 `key` 的优先级：

1. 命令行 `--key`
2. 当前目录 `qq_map_cli_config.json`
3. 环境变量 `QQ_MAP_KEY`

## 常用命令示例

### 地址转经纬度

```bash
python3 qq_map_cli.py geocoder \
  --address "北京市海淀区彩和坊路海淀西大街74号"
```

### 两个地址之间距离

```bash
python3 qq_map_cli.py address-distance \
  --from-address "北京市海淀区中关村大街27号" \
  --to-address "北京市朝阳区望京街10号" \
  --mode driving
```

### 距离矩阵

```bash
python3 qq_map_cli.py distance-matrix \
  --origin 39.984154,116.307490 \
  --destination 39.908692,116.397477 \
  --mode walking
```
