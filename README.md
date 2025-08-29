# Ren'Py 对话导入工具

一个用于从 `.tab` 表格中批量更新游戏脚本、添加语音、更新翻译标识符的小工具
简单来说就是错别字更新器，最适用的场景是游戏演出编写与翻译工作都完成了结果回头发现一大堆错别字时时需要绝望地挨个儿修改的时候。

~~不要问我为什么要搓这个~~

## 功能特点

- **📝 更新剧情文本**：根据 `.tab` 表格里的 `Identifier`替换 `.rpy` 脚本里对应的对话内容。不用行号匹配。但注意不能增删行，且必须保证你用的 `.tab` 表格是最新的（导出表格后要是改了脚本文本，会导致修改的脚本文件中的Identifier变更，因此就会`.tab`文件对不上了

- **🎵 插入语音标记**：自动添加 `voice "file.ogg"` 行，在表格里新建一列，表头写上 `"voice"`，下面填好文件名（不用加引号）。运行工具时勾选选项，就能批量在对话前插入语音代码。适合只有零星几句语音，或者大量复用同一语音的情况。如果你有完整多语言配音，**就没有必要使用这个了！**！官方自带的自动匹配更香XD
  
- **🆔 更新标识符**：修改文本后，语句的 `Identifier` 会变。这个功能能把新的 `Identifier` 写回你的 `.tab` 表格里，方便你下轮继续编辑。
  
- **🌍 更新翻译文件**：当 `Identifier` 变了，旧的翻译就会失效。这个功能会同步更新翻译文件里的 `Identifier`，并贴心地加一句 `#翻译待更新` 注释，帮你快速定位哪些翻译需要返工（顺便还会标记修改次数，跑了几遍就会x几，用来计算到底修了多少次（草
  
- **🔤 多编码支持**：支持 UTF-8 和 GBK 编码的文件（tmd，一用excel编辑tab表格就会强制变成gbk编码表！

## 怎么用？

### 1. 安装工具
1. 下载 `input_dialogue.rpy` 和 `schinese.rpy`。
    - `input_dialogue.rpy` 是功能代码。
    - `schinese.rpy` 是中文翻译。
2. 把 `input_dialogue.rpy` 放进 `你的项目/renpy/launcher/game/` 中。
3. 把 `schinese.rpy` 放进 `你的项目/renpy/launcher/game/tl/schinese/` 中。


### 2. 添加入口
打开 `你的项目/renpy/launcher/game/front_page.rpy`，找到类似下面的代码块：
```rpy
textbutton _("Force Recompile") action Jump("force_recompile")
```
在它下面添加一行：
```rpy
textbutton _("Import Dialogue") action Jump("import_dialogue")
```
现在打开 Ren'Py 启动器，就能在列表中看到“**批量更新对话**”的入口了！


### 3. 准备 `.tab` 文件
请使用 Ren'Py 自带的“**提取对话**”功能来获取 `.tab` 文件。

**提取时务必注意：**
1.  选择“**以制表符分隔的表格 (dialogue.tab)**”。
2.  **不要勾选**另外三个选项（否则提取的内容会没有 texttag，一覆盖你的texttag也就没了）。
3.  默认语言填 `None`。

你的表格文件应至少包含以下列：
- `identifier` – 每行的唯一标识符
- `filename` – `.rpy` 文件的相对路径
- `character` – 角色名（可选）
- `dialogue` – 对话文本
- `line number` – 脚本中的行号

**可选列：**
- `voice` – 语音文件名（例如 `voice_01`）


### 4. 运行工具
1.  打开 Ren'Py 启动器。
2.  选择你的项目。
3.  点击“**批量更新对话**”。
4.  选择你的 `.tab` 文件并勾选需要的处理选项。
5.  **备份备份备份！！！！！！！！！！**
6.  点击 **处理文件**，祈祷吧！ 


## 选项说明书

| 选项 | 说明 |
|------|------|
| **更新文本内容** | 将 TAB 表中的文本替换到 `.rpy` 文件里对应 Identifier 的文本上。 |
| **插入语音标记** | 在对话行上方插入 `voice "voice_01"` 行。 |
| **更新对话标识符** | 如果更新文本后 Identifier 变了，把新 Identifier 写回你的 `.tab` 文件里。 |
| **更新翻译字符串** | 如果 Identifier 变了，同步更新翻译文件里的 Identifier 并添加注释。 |


## 要求

- Ren'Py 7.4.0 或更高版本
- 一个已经通过“提取对话”功能处理过的 Ren'Py 项目


## ⚠️ 重要警告！

- **运行工具前务必备份你的项目！切记！！！！**
- 工具会为修改的文件创建 `.bak` 备份文件。
- 如果更新标识符，翻译文件会同步更新并添加警告注释。
- **关于角色名判断**：这个工具是在中文环境下诞生的，所以它判断 `character` 列是变量还是临时字符串的方法很简单粗暴——**看里面有没有中文**！如果没有中文，就认为是定义好的角色变量名（草率但有效.jpg）。

---

# Ren'Py Tab Importer Tool

A lifesaver tool to pull you out of the despair of typo hell! It's designed for batch updating game scripts from `.tab` files, adding voice lines, and updating translation identifiers.

In short, this is your "I regret everything" button. It's most useful in that nightmare scenario where all the game acting and translation are done, you look back—**"Oh crap, a bunch of typos!"**—and face the despair of fixing them one by one.
~~Don't ask me why I felt the need~~

## What Can It Do?

- **📝 Update Story Text**: Precisely replaces dialogue text in `.rpy` scripts based on the `Identifier` in the `.tab` file. No line number matching needed! But note: You cannot add or delete lines, and you MUST use the latest `.tab` file (if you modify the script text after exporting the table, the Identifier won't match and it will fail for that line!).
  
- **🎵 Insert Voice Tags**: Automatically adds `voice "file.ogg"` lines! Create a new column in your table named `"voice"`, fill in the filenames (without quotes). Check the option when running the tool to batch insert voice code before dialogues. Perfect for projects with just a few voice lines or heavy voice reuse. **Do NOT use this** if you have full multi-language voiceovers! The official automatic matching is better.
  
- **🆔 Update Identifiers**: Modifying text changes the statement's `Identifier`. This feature writes the new `Identifier` back to your `.tab` file, making the next round of editing easier.
  
- **🌍 Update Translation Files**: When the `Identifier` changes, old translations break. This feature synchronizes the new `Identifier` into the translation files and kindly adds a `# Translation needs update` comment, helping you quickly locate which translations need work (It also marks how many times it's been modified—an 'x' followed by the count—so you know exactly how much you've been messing around 😂).
  
- **🔤 Multi-Encoding Support**: Handles files in both UTF-8 and GBK encodings (**Darn it, Excel always forces `.tab` files into GBK!**).

## How to Use?

### 1. Install the Tool
1. Download `input_dialogue.rpy` and `schinese.rpy`.
    - `input_dialogue.rpy` is the core functionality.
    - `schinese.rpy` is the Chinese translation (for the tool's UI).
2. Place `input_dialogue.rpy` into `YourProject/renpy/launcher/game/`.
3. Place `schinese.rpy` into `YourProject/renpy/launcher/game/tl/schinese/`.

### 2. Add the Entry Point
Open `YourProject/renpy/launcher/game/front_page.rpy`, find a code block like this:
```rpy
textbutton _("Force Recompile") action Jump("force_recompile")
```
Add this line right after it:
```rpy
textbutton _("Import Dialogue") action Jump("import_dialogue")
```
Now open the Ren'Py Launcher, and you'll see the "**Import Dialogue**" button in the list!

### 3. Prepare the `.tab` File
Use Ren'Py's built-in "**Extract Dialogue**" feature to get your `.tab` file.

**Extraction Notes (IMPORTANT):**
1.  Choose "**Tab-delimited Spreadsheet (dialogue.tab)**".
2.  **DO NOT check** the other three options (or the extracted content will lack texttags and fail to update).
3.  Set Default Language to `None`.

Your spreadsheet must at least contain these columns:
- `identifier` – The unique identifier for each line
- `filename` – The relative path to the `.rpy` file
- `character` – The character's name (Optional)
- `dialogue` – The dialogue text
- `line number` – The line number in the script

**Optional Column:**
- `voice` – The voice filename (e.g., `voice_01`)

### 4. Run the Tool
1.  Open the Ren'Py Launcher.
2.  Select your project.
3.  Click "**Import Dialogue**".
4.  Select your `.tab` file and choose the processing options you need.
5.  Click **Process Files** and pray! (Just kidding, but backup is highly recommended)

## Option Manual

| Option | Description |
|------|------|
| **Update Text Content** | Replaces the text in `.rpy` files for the corresponding Identifier with the text from the TAB file. |
| **Insert Voice Tags** | Inserts a `voice "voice_01"` line above the dialogue line. |
| **Update Dialogue Identifiers** | If the Identifier changes after updating text, writes the new Identifier back to your `.tab` file. |
| **Update Translation Strings** | If the Identifier changes, updates the Identifier in the translation file and adds a comment. |

## Requirements

- Ren'Py 7.4.0 or higher
- A Ren'Py project that has been processed with the "Extract Dialogue" feature

## ⚠️ Important Warnings!

- **ALWAYS BACKUP YOUR PROJECT BEFORE RUNNING THIS TOOL! SERIOUSLY!!!!**
- The tool creates `.bak` backup files for modified files.
- If updating identifiers, translation files will be updated and get warning comments.
- **About Character Name Detection**: This tool was born in a Chinese environment, so its method to determine if the `character` column is a variable or a temporary string is simple and crude—**check if it contains Chinese characters**! If it doesn't, it's assumed to be a predefined character variable (Effective.jpg).

---
