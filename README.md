# MCMOD 百科 MCP Server

MC百科 (mcmod.cn) 查询工具，提供 Minecraft 模组信息查询功能。

## 功能

| 工具 | 说明 | 示例 |
|-----|------|------|
| `mcmod_search` | 搜索模组/整合包/物品/教程 | `mcmod_search("机械动力", "mod")` |
| `mcmod_find_mod` | 通过名称查找模组 ID | `mcmod_find_mod("AE2")` |
| `mcmod_get_mod` | 获取模组详情（含MC版本） | `mcmod_get_mod(2021)` |
| `mcmod_find_modpack` | 通过名称查找整合包 ID | `mcmod_find_modpack("机械动力")` |
| `mcmod_get_modpack` | 获取整合包详情 | `mcmod_get_modpack(549)` |
| `mcmod_list_items` | 获取模组物品列表 | `mcmod_list_items(2021, 1)` |
| `mcmod_get_item` | 获取物品详情 | `mcmod_get_item(196531)` |
| `mcmod_list_tutorials` | 获取模组教程列表 | `mcmod_list_tutorials(2021)` |
| `mcmod_get_tutorial` | 获取教程内容 | `mcmod_get_tutorial(2373)` |
| `mcmod_hot_mods` | 获取热门/推荐模组 | `mcmod_hot_mods("tech", 15)` |
| `mcmod_random_mod` | 随机推荐一个模组 | `mcmod_random_mod()` |

## 搜索类型

`mcmod_search` 支持以下搜索类型：
- `all` - 全部
- `mod` - 模组
- `modpack` - 整合包
- `item` - 物品（会显示所属模组）
- `post` - 教程

## 物品类型

`mcmod_list_items` 支持以下物品类型：
- `1` - 物品/方块
- `4` - 生物
- `5` - 附魔
- `7` - 多方块
- `9` - 热键
- `10` - 游戏设定

## 模组分类

`mcmod_hot_mods` 支持以下分类：
- `all` - 全部/首页推荐
- `tech` - 科技
- `magic` - 魔法
- `adventure` - 冒险
- `farming` - 农业
- `decoration` - 装饰
- `misc` - 杂项

## 安装运行

```bash
cd evil/mcp/mcmod-mcp
uv sync
uv run server.py
```

## MCP 配置

添加到 `.kiro/settings/mcp.json`：

```json
{
  "mcpServers": {
    "mcmod": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/evil/mcp/mcmod-mcp", "server.py"]
    }
  }
}
```

## 常用模组 ID

| 模组 | ID |
|-----|-----|
| 机械动力 (Create) | 2021 |
| 应用能源2 (AE2) | 260 |
| 工业时代2 (IC2) | 2 |
| 热力膨胀 (TE) | 335 |
| 匠魂 (TiC) | 74 |
| 格雷科技6 (GT6) | 411 |
| 沉浸工程 (IE) | 463 |
