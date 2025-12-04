"""
MCMOD 百科 MCP Server
提供 MC 百科 (mcmod.cn) 的查询功能
"""

import re
import asyncio
from typing import Optional
from mcp.server.fastmcp import FastMCP
import httpx
from bs4 import BeautifulSoup
import time

mcp = FastMCP("mcmod-mcp")

BASE_URL = "https://www.mcmod.cn"
SEARCH_URL = "https://search.mcmod.cn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
}

# 简单缓存 (URL -> (timestamp, content))
_cache: dict[str, tuple[float, str]] = {}
CACHE_TTL = 300  # 5 分钟


async def fetch_page(url: str, use_cache: bool = True, retries: int = 3) -> Optional[BeautifulSoup]:
    """获取并解析页面，支持缓存和重试，验证内容完整性"""
    # 检查缓存
    if use_cache and url in _cache:
        ts, html = _cache[url]
        if time.time() - ts < CACHE_TTL:
            return BeautifulSoup(html, "html.parser")

    # 判断是否为搜索页面
    is_search = "search.mcmod.cn" in url
    min_length = 30000 if is_search else 5000  # 搜索页面应该更大

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text

                # 验证内容完整性
                if len(html) < min_length:
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    # 最后一次尝试，接受较短的内容
                    if len(html) > 1000:
                        _cache[url] = (time.time(), html)
                        return BeautifulSoup(html, "html.parser")
                    return None

                _cache[url] = (time.time(), html)
                return BeautifulSoup(html, "html.parser")
        except Exception:
            if attempt < retries:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            return None
    return None


def extract_id_from_url(url: str, pattern: str) -> Optional[str]:
    """从 URL 提取 ID"""
    match = re.search(pattern, url)
    return match.group(1) if match else None


@mcp.tool()
async def mcmod_search(keyword: str, search_type: str = "all", limit: int = 10) -> str:
    """
    搜索 MC 百科

    Args:
        keyword: 搜索关键词
        search_type: 搜索类型 - all(全部), mod(模组), modpack(整合包), item(物品), post(教程)
        limit: 返回结果数量，默认 10
    """
    # filter: 1=模组, 2=整合包, 3=物品, 4=教程
    type_map = {"all": "", "mod": "&filter=1", "modpack": "&filter=2", "item": "&filter=3", "post": "&filter=4"}
    filter_param = type_map.get(search_type, "")
    url = f"{SEARCH_URL}/s?key={keyword}{filter_param}"

    soup = await fetch_page(url, use_cache=False)
    if not soup:
        return "搜索失败，请检查网络连接后重试"

    results = []
    seen = set()

    # 支持两种结果容器: .result-item 和 .search-result-list 内的内容
    for item in soup.select(".result-item, .search-result-list > div")[:limit * 3]:
        text = item.get_text(" ", strip=True)

        # 查找所有链接
        for link in item.select("a[href*='.html']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)

            # 跳过无效链接
            if "/category/" in href:
                continue
            if not title or title.startswith("www.") or title.startswith("http"):
                continue

            # 识别类型
            item_id = None
            if "/class/" in href:
                item_id = extract_id_from_url(href, r"/class/(\d+)")
                item_type = "模组"
            elif "/modpack/" in href:
                item_id = extract_id_from_url(href, r"/modpack/(\d+)")
                item_type = "整合包"
            elif "/item/" in href and "/item/list/" not in href:
                item_id = extract_id_from_url(href, r"/item/(\d+)")
                item_type = "物品"
            elif "/post/" in href:
                item_id = extract_id_from_url(href, r"/post/(\d+)")
                item_type = "教程"
            else:
                continue

            if item_id and item_id not in seen:
                seen.add(item_id)
                entry = f"- [{item_type}] {title} (ID: {item_id})"
                results.append(entry)
                break

        if len(results) >= limit:
            break

    if not results:
        # 检查是否有"未找到"提示
        no_result = soup.select_one(".search-result")
        if no_result and "没有找到" in no_result.get_text():
            return f"MC百科未收录与 '{keyword}' 相关的内容"
        return f"未找到与 '{keyword}' 相关的结果"

    return f"搜索 '{keyword}' 的结果 ({len(results)}条):\n\n" + "\n".join(results)


@mcp.tool()
async def mcmod_get_mod(mod_id: int) -> str:
    """
    获取模组详情

    Args:
        mod_id: 模组 ID，如 2021 (机械动力)、6 (应用能源2)
    """
    url = f"{BASE_URL}/class/{mod_id}.html"
    soup = await fetch_page(url)
    if not soup:
        return f"获取模组 {mod_id} 失败，请检查 ID 是否正确"

    result = [f"模组 ID: {mod_id}"]

    # 提取名称
    name_cn = soup.select_one("h3")
    name_en = soup.select_one("h4")
    if name_cn:
        result.append(f"中文名: {name_cn.get_text(strip=True)}")
    if name_en:
        result.append(f"英文名: {name_en.get_text(strip=True)}")

    # 提取信息
    info_left = soup.select_one(".class-info-left")
    if info_left:
        text = info_left.get_text(" ", strip=True)
        for field, pattern in [
            ("支持平台", r"支持平台:\s*([^运作]+)"),
            ("运作方式", r"运作方式:\s*([^运行]+)"),
            ("运行环境", r"运行环境:\s*([^收录]+)"),
        ]:
            match = re.search(pattern, text)
            if match:
                result.append(f"{field}: {match.group(1).strip()}")

    # 提取简介
    intro = soup.select_one(".text-area.common-text")
    if intro:
        intro_text = intro.get_text(" ", strip=True)[:600]
        result.append(f"\n简介:\n{intro_text}...")

    # 提取资料统计
    type_links = soup.select("a[href*='/item/list/']")
    if type_links:
        stats = []
        for link in type_links[:6]:
            text = link.get_text(strip=True)
            if text and "(" in text:
                stats.append(text)
        if stats:
            result.append(f"\n资料统计: {', '.join(stats)}")

    result.append(f"\n页面链接: {url}")
    return "\n".join(result)


@mcp.tool()
async def mcmod_list_items(mod_id: int, item_type: int = 1, limit: int = 30) -> str:
    """
    获取模组的物品/方块列表

    Args:
        mod_id: 模组 ID
        item_type: 类型 - 1(物品/方块), 4(生物), 5(附魔), 7(多方块), 9(热键), 10(游戏设定)
        limit: 返回数量，默认 30
    """
    url = f"{BASE_URL}/item/list/{mod_id}-{item_type}.html"
    soup = await fetch_page(url)
    if not soup:
        return f"获取物品列表失败，请检查模组 ID {mod_id} 是否正确"

    items = []
    seen = set()

    for link in soup.select("a[href*='/item/'][href$='.html']"):
        href = link.get("href", "")
        if "/item/list/" in href or "/item/add/" in href:
            continue

        item_id = extract_id_from_url(href, r"/item/(\d+)\.html")
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)

        name = link.get_text(strip=True)
        name_en = link.get("data-en", "")
        if name:
            display = f"- {name}"
            if name_en:
                display += f" ({name_en})"
            display += f" [ID: {item_id}]"
            items.append(display)

    if not items:
        return f"模组 {mod_id} 暂无该类型 (type={item_type}) 的物品数据"

    type_names = {1: "物品/方块", 4: "生物", 5: "附魔", 7: "多方块", 9: "热键", 10: "游戏设定"}
    type_name = type_names.get(item_type, "物品")
    header = f"模组 {mod_id} 的{type_name}列表 (共{len(items)}项"
    if len(items) > limit:
        header += f"，显示前{limit}项"
    header += "):\n\n"
    return header + "\n".join(items[:limit])


@mcp.tool()
async def mcmod_get_item(item_id: int) -> str:
    """
    获取物品/方块详情

    Args:
        item_id: 物品 ID，如 196531 (水车)、196521 (传动杆)
    """
    url = f"{BASE_URL}/item/{item_id}.html"
    soup = await fetch_page(url)
    if not soup:
        return f"获取物品 {item_id} 失败，请检查 ID 是否正确"

    result = [f"物品 ID: {item_id}"]

    # 物品名称
    name = soup.select_one("span.name, h5")
    if name:
        result.append(f"名称: {name.get_text(strip=True)}")

    # 所属模组
    mod_link = soup.select_one("a[href*='/class/'][href$='.html']")
    if mod_link:
        mod_name = mod_link.get_text(strip=True)
        mod_id_str = extract_id_from_url(mod_link.get("href", ""), r"/class/(\d+)")
        if mod_name and mod_id_str:
            result.append(f"所属模组: {mod_name} (ID: {mod_id_str})")

    # 合成配方 (玩家最关心的信息)
    recipes = soup.select("td.text.item-table-count")
    if recipes:
        recipe_list = []
        for r in recipes[:3]:
            recipe_text = r.get_text(" ", strip=True)
            if recipe_text and "↓" in recipe_text:
                # 简化格式
                recipe_text = recipe_text.replace("标签: ", "").replace("minecraft:", "")
                recipe_list.append(f"  • {recipe_text}")
        if recipe_list:
            result.append(f"\n合成配方:")
            result.extend(recipe_list)

    # 物品介绍
    intro = soup.select_one(".item-content.common-text")
    if intro:
        intro_text = intro.get_text(" ", strip=True)[:1000]
        result.append(f"\n介绍:\n{intro_text}")

    result.append(f"\n页面链接: {url}")
    return "\n".join(result)


@mcp.tool()
async def mcmod_list_tutorials(mod_id: int, limit: int = 15) -> str:
    """
    获取模组的教程列表

    Args:
        mod_id: 模组 ID
        limit: 返回数量，默认 15
    """
    url = f"{BASE_URL}/class/{mod_id}.html"
    soup = await fetch_page(url)
    if not soup:
        return f"获取教程列表失败，请检查模组 ID {mod_id} 是否正确"

    tutorials = []
    seen = set()

    for link in soup.select("a[href*='/post/']"):
        href = link.get("href", "")
        if "/post/add" in href or "bbs.mcmod.cn" in href:
            continue

        post_id = extract_id_from_url(href, r"/post/(\d+)")
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)

        title = link.get_text(strip=True)
        if title and len(title) > 2:
            full_href = href if href.startswith("http") else f"{BASE_URL}{href}"
            tutorials.append(f"- {title} [ID: {post_id}]\n  {full_href}")

    if not tutorials:
        return f"模组 {mod_id} 暂无教程"

    header = f"模组 {mod_id} 的教程列表 (共{len(tutorials)}篇):\n\n"
    return header + "\n\n".join(tutorials[:limit])


@mcp.tool()
async def mcmod_get_tutorial(post_id: int) -> str:
    """
    获取教程内容

    Args:
        post_id: 教程 ID，如 2373 (机械动力教程目录)
    """
    url = f"{BASE_URL}/post/{post_id}.html"
    soup = await fetch_page(url)
    if not soup:
        return f"获取教程 {post_id} 失败，请检查 ID 是否正确"

    result = [f"教程 ID: {post_id}"]

    # 标题
    title = soup.select_one(".post-title h5, h1, .title")
    if title:
        result.append(f"标题: {title.get_text(strip=True)}")

    # 所属模组
    mod_link = soup.select_one("a[href*='/class/'][href$='.html']")
    if mod_link:
        mod_name = mod_link.get_text(strip=True)
        mod_id_str = extract_id_from_url(mod_link.get("href", ""), r"/class/(\d+)")
        if mod_name and mod_id_str:
            result.append(f"所属模组: {mod_name} (ID: {mod_id_str})")

    # 正文内容
    content = soup.select_one(".post-content, .common-text, .text-area")
    if content:
        for tag in content.select("script, style"):
            tag.decompose()
        text = content.get_text("\n", strip=True)
        if len(text) > 2500:
            text = text[:2500] + "\n\n[内容过长，已截断，请访问原页面查看完整内容]"
        result.append(f"\n内容:\n{text}")

    result.append(f"\n页面链接: {url}")
    return "\n".join(result)


@mcp.tool()
async def mcmod_find_mod(name: str) -> str:
    """
    通过名称查找模组 ID（搜索模组并返回匹配结果）

    Args:
        name: 模组名称，如 "机械动力"、"Create"、"AE2"
    """
    # 使用全局搜索，结果更准确
    url = f"{SEARCH_URL}/s?key={name}"
    soup = await fetch_page(url, use_cache=False)
    if not soup:
        return "搜索失败，请检查网络连接"

    results = []
    seen = set()

    # 查找所有模组链接
    for link in soup.select("a[href*='/class/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)

        # 跳过无效链接
        if "/category/" in href:
            continue
        if not title or len(title) < 2:
            continue
        if title.startswith("www.") or title.startswith("http") or "mcmod.cn" in title:
            continue

        mod_id = extract_id_from_url(href, r"/class/(\d+)")
        if mod_id and mod_id not in seen:
            seen.add(mod_id)
            results.append(f"- {title} (ID: {mod_id})")

        if len(results) >= 8:
            break

    if not results:
        return f"未找到名为 '{name}' 的模组"

    return f"搜索 '{name}' 找到的模组:\n\n" + "\n".join(results) + "\n\n使用 mcmod_get_mod(ID) 获取详情"


@mcp.tool()
async def mcmod_get_modpack(modpack_id: int) -> str:
    """
    获取整合包详情

    Args:
        modpack_id: 整合包 ID，如 549 (机械动力：锄与锤)
    """
    url = f"{BASE_URL}/modpack/{modpack_id}.html"
    soup = await fetch_page(url)
    if not soup:
        return f"获取整合包 {modpack_id} 失败，请检查 ID 是否正确"

    result = [f"整合包 ID: {modpack_id}"]

    # 名称
    name = soup.select_one("h3")
    if name:
        result.append(f"名称: {name.get_text(strip=True)}")

    # 提取信息
    info_left = soup.select_one(".class-info-left")
    if info_left:
        text = info_left.get_text(" ", strip=True)
        for field, pattern in [
            ("整合包类型", r"整合包类型:\s*([^运作]+)"),
            ("运作方式", r"运作方式:\s*([^打包]+)"),
            ("打包方式", r"打包方式:\s*([^收录]+)"),
            ("MC版本", r"支持的MC版本:\s*([^整合包作者]+)"),
            ("作者", r"整合包作者:\s*([^显示]+)"),
        ]:
            match = re.search(pattern, text)
            if match:
                result.append(f"{field}: {match.group(1).strip()}")

    # 简介
    intro = soup.select_one(".text-area.common-text")
    if intro:
        intro_text = intro.get_text(" ", strip=True)[:800]
        result.append(f"\n简介:\n{intro_text}")

    # 包含的模组
    mod_links = soup.select("a[href*='/class/'][href$='.html']")
    if mod_links:
        mods = []
        seen = set()
        for link in mod_links[:15]:
            mod_name = link.get_text(strip=True)
            href = link.get("href", "")
            if "/category/" in href or not mod_name:
                continue
            mod_id = extract_id_from_url(href, r"/class/(\d+)")
            if mod_id and mod_id not in seen:
                seen.add(mod_id)
                mods.append(f"{mod_name} (ID: {mod_id})")
        if mods:
            result.append(f"\n包含模组: {', '.join(mods[:10])}")
            if len(mods) > 10:
                result.append(f"...等共 {len(mods)} 个模组")

    result.append(f"\n页面链接: {url}")
    return "\n".join(result)


@mcp.tool()
async def mcmod_find_modpack(name: str) -> str:
    """
    通过名称查找整合包 ID

    Args:
        name: 整合包名称，如 "机械动力"、"科技"
    """
    url = f"{SEARCH_URL}/s?key={name}&filter=2"
    soup = await fetch_page(url, use_cache=False)
    if not soup:
        return "搜索失败，请检查网络连接"

    results = []
    seen = set()

    for item in soup.select(".result-item")[:10]:
        for link in item.select("a[href*='/modpack/'][href$='.html']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if not title or title.startswith("www.") or title.startswith("http"):
                continue

            modpack_id = extract_id_from_url(href, r"/modpack/(\d+)")
            if modpack_id and modpack_id not in seen:
                seen.add(modpack_id)
                results.append(f"- {title} (ID: {modpack_id})")
                break

        if len(results) >= 5:
            break

    if not results:
        return f"未找到名为 '{name}' 的整合包"

    return f"搜索 '{name}' 找到的整合包:\n\n" + "\n".join(results) + "\n\n使用 mcmod_get_modpack(ID) 获取详情"


if __name__ == "__main__":
    mcp.run()
