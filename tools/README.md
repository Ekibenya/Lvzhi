# 卡的源码树与工具链

主文档 `core/vendor/three/build/chunks/9d717bc0/156a50943028.html` 是**产物**，不是底稿。
卡的正文全部打包成里面的一行 JSON（`<script id="cardLuzhi">` → `window.__GAME_LUZHI__`），
那一行不适合手改：一个引号错位，整张卡就废了。

底稿在 `st/data/`。改卡改这里，然后注回主文档。

```
st/data/
  meta.json            panelSpec 与卡元字段（name / description / personality /
                       scenario / system_prompt / post_history_instructions /
                       mes_example / first_mes）
  openings/NN.md       开局。首行一个 JSON 头 {"era","scene","year"}，空行，正文
  briefs.json          选局环确认弹窗的一句话简介，键是开局号的字符串
  lore/core.json       常驻世界书条目（constant），强制排最前
  lore/aNN-类.json     其余条目。文件名序 == 世界书顺序，所以序号不要乱改
```

## 三个脚本

| 脚本 | 方向 | 干什么 |
|---|---|---|
| `cardbuild.py` | `st/data/` → 主文档 | 组装并注入。改完卡跑这个 |
| `carddump.py`  | 主文档 → `st/data/` | 反向拆解。只在底稿丢了、或要从别的产物里捞卡的时候用 |
| `cardcheck.py` | 只读 | 注入前自检：编号、槽位、禁字、顺序 |

```sh
python3 tools/cardcheck.py     # 先看一眼
python3 tools/cardbuild.py     # 再注入
```

两个方向是无损互逆的：`carddump.py` 拆完再 `cardbuild.py` 装回去，主文档逐字节不变。
这条性质是回归测试的地基 —— 改动工具链之后请重新验一次。

## 线号

线号由环境变量 `ROMA_LINE` 决定（默认 `luzhi`），三处标识随之推出：

```
<script id="cardLuzhi">   window.__GAME_LUZHI__   var BRIEFS={luzhi:…}
```

换新线只改这一个环境变量，脚本里不留任何一条线的名字。

## 注入前的硬闸

`cardbuild.py` 会扫描将要注入的全部正文，命中即拒绝写入：

- **禁字**：工具与模型的牌子名一律不许进正文，一个都不行
- **串戏词**：别条线的主角名混进本卡（多半是复制粘贴带过来的）

拒绝的时候主文档一个字节都不会动，放心重跑。

## 空白模板

`st/blank/` 是掏空的这张卡：结构、面板、二十一条铁则的槽位、开局与世界书的字段形状
全部留着，与某一条线绑定的正文换成 `«…»` 槽位。

通用的手艺条款（文风、口语度、不许制造意义、禁语、恶从欲望来、脏话与骂法、
暴力写感官、一幕只有一个人有里子、只知道到今年为止）是逐字留下的 —— 那几条不挑题材，
是这张卡真正值钱的部分。与世界绑定的条款（族群正典、世界前提、人物正典、核心机制、
不许串朝代的词表）挖成了槽位。

开新卡：

```sh
cp -r st/blank st/data          # 注意：会盖掉现有底稿，先确认 st/data 已提交
grep -rn '«' st/data            # 槽位清单，逐个填掉
python3 tools/cardcheck.py      # 填完自检
```

`cardcheck.py` 在还有 `«` 没填掉的时候会报出来 —— 空模板本身注入是能过的，
所以这一步靠自检拦，别靠注入报错。
