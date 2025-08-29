label import_dialogue:
    python:
        import os
        import re
        import io
        import shutil

        def read_text_file_guess_encoding(path):
            try:
                with io.open(path, 'r', encoding='utf-8') as f:
                    return f.read(), 'utf-8'
            except UnicodeDecodeError:
                with io.open(path, 'r', encoding='gbk') as f:
                    return f.read(), 'gbk'

        def write_text_file(path, text, encoding):
            with io.open(path, 'w', encoding=encoding, newline='') as f:
                f.write(text)

        def parse_tab_file(path):
            content, enc = read_text_file_guess_encoding(path)
            lines = content.splitlines()
            if not lines:
                raise Exception("Empty tab file: " + path)
            headers = [h.strip().lower() for h in lines[0].split('\t')]
            rows = []
            for ln, line in enumerate(lines[1:], start=2):
                if not line.strip():
                    continue
                parts = line.split('\t')
                if len(parts) < len(headers):
                    parts += [''] * (len(headers) - len(parts))
                row = {headers[i]: parts[i] if i < len(parts) else '' for i in range(len(headers))}
                rows.append(row)
            return headers, rows, enc

        def save_tab_file(path, headers, rows, encoding='utf-8'):
            # 保持原有列顺序输出
            out_lines = []
            out_lines.append('\t'.join(headers))
            for r in rows:
                out_lines.append('\t'.join([r.get(h, '') for h in headers]))
            write_text_file(path, '\n'.join(out_lines) + '\n', encoding)

        def ensure_required_columns(headers, required):
            hset = set(headers)
            missing = [c for c in required if c not in hset]
            if missing:
                raise Exception("Missing required columns: " + ", ".join(missing))

        def as_int(s, default=None):
            try:
                return int(str(s).strip())
            except:
                return default

        def escape_renpy_string(s, quote='"'):
            # 简单转义，避免破坏行
            s = s.replace('\\', '\\\\')
            if quote == '"':
                s = s.replace('"', '\\"')
            else:
                s = s.replace("'", "\\'")
            # 保留换行、标签等
            return s

        def replace_first_string_literal(line, new_text):
            # 在一行中找到第一对引号里的内容，替换之。支持 "..." 或 '...'
            # 返回 (新行, 使用的引号, 起始索引, 结束索引) 或 (None, None, None, None) 表示失败
            # 忽略#之后的注释（若#在引号前则认为整行是注释）
            # 简化处理，不考虑三引号
            # 找到第一个引号前若存在 # 则认为注释，放弃
            qpos = len(line)
            qchar = None
            for i, ch in enumerate(line):
                if ch in ('"', "'"):
                    qpos = i
                    qchar = ch
                    break
                if ch == '#':
                    # 注释在引号前，放弃
                    return None, None, None, None

            if qchar is None:
                return None, None, None, None

            # 寻找结束引号，处理转义
            i = qpos + 1
            escaped = False
            while i < len(line):
                c = line[i]
                if escaped:
                    escaped = False
                elif c == '\\':
                    escaped = True
                elif c == qchar:
                    # 找到结束
                    start = qpos
                    end = i
                    new_content = escape_renpy_string(new_text, qchar)
                    new_line = line[:start+1] + new_content + line[end:]
                    return new_line, qchar, start, end
                i += 1

            # 未找到结束引号
            return None, None, None, None

        def try_update_character_token(line, desired_char):
            # 将第一对引号之前的最后一个“令牌”替换成desired_char。
            # desired_char为空时，尽量删除该令牌。
            # 仅处理形如 "<indent><token><spaces>\"..." 的简单情况，复杂情况保留原样。
            # 返回 (新行, 是否修改)
            m = re.match(r'^(\s*)(.*?)(["\'])', line)
            if not m:
                return line, False
            indent = m.group(1)
            before = m.group(2)
            quote = m.group(3)

            # 若before为空或纯空白，无需替换角色（旁白）
            if before.strip() == '':
                if desired_char:
                    # 需要加上角色令牌
                    return f'{indent}{desired_char} {quote}' + line[m.end():], True
                else:
                    return line, False

            # 有内容，尝试把最后一个“非空白序列”视为角色名
            # 例如： "e    "  -> 替换 e
            tokens = re.split(r'(\s+)', before)
            # tokens 结构: token, space, token, space, ...
            # 找到最后一个非空白token的索引
            idx = None
            for i in range(len(tokens)-1, -1, -1):
                if tokens[i].strip() != '':
                    idx = i
                    break
            if idx is None:
                # 全是空白
                if desired_char:
                    return f'{indent}{desired_char} {quote}' + line[m.end():], True
                else:
                    return line, False

            # 若desired_char为空，删除该token以及其左侧可能的一个空格
            if not desired_char:
                # 去掉该token，且若其左邻是空白一并去掉
                new_tokens = tokens[:]
                new_tokens[idx] = ''
                if idx-1 >= 0 and new_tokens[idx-1].strip() == '':
                    new_tokens[idx-1] = ''
                new_before = ''.join(new_tokens)
                return f'{indent}{new_before}{quote}' + line[m.end():], True
            else:
                tokens[idx] = desired_char
                # 若角色名后没有空格，则补一个空格
                if idx+1 >= len(tokens) or tokens[idx+1].strip() != '':
                    tokens.insert(idx+1, ' ')
                new_before = ''.join(tokens)
                return f'{indent}{new_before}{quote}' + line[m.end():], True

        def insert_or_replace_voice(lines, idx, old_id,voice_value):
            # 在idx所指向的台词行之前，插入或替换 voice "xxx"
            # 返回新lines，返回插入/替换后的台词行行号（可能变化）
            if idx < 0 or idx >= len(lines):
                return lines, idx
            # 获取缩进
            m = re.match(r'^(\s*)', lines[idx])
            indent = m.group(1) if m else ''
            if voice_value != None and voice_value != "":
                voice_value = voice_value.strip()
                if voice_value.startswith('voice '):
                    voice_line = f'{indent}{voice_value.rstrip()}\n'
                else:
                    voice_line = f'{indent}voice "{voice_value}"\n'
                # 若上一行已有voice则替换，否则插入


                # 更新翻译文本值
                pattern = re.compile(r'^(translate\s+\w+\s+' + re.escape(old_id) + r':)(.*?)(?=^translate|\Z)', re.MULTILINE | re.DOTALL)
                
                for file_path in tl_files:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 查找所有匹配的代码块
                        matches = pattern.findall(content)
                        
                        if not matches:
                            continue
                            
                        # 对每个匹配的代码块进行处理
                        for match in matches:
                            original_block = match[0] + match[1]
                            
                            # 检查是否已有voice行
                            voice_pattern = re.compile(r'^\s*voice\s+".*?"', re.MULTILINE)
                            has_voice = voice_pattern.search(match[1])
                            
                            if has_voice:
                                # 替换现有的voice值
                                updated_content = voice_pattern.sub(f'    voice "{voice_value}"', match[1])
                            else:
                                # 添加新的voice行
                                # 找到第一个非注释行和非空行的位置
                                lines = match[1].split('\n')
                                insert_pos = 0
                                for i, line in enumerate(lines):
                                    if line.strip() and not line.strip().startswith('#'):
                                        insert_pos = i
                                        break
                                
                                # 在第一个非注释行前插入voice行
                                lines.insert(insert_pos, f'    voice "{voice_value}"')
                                updated_content = '\n'.join(lines)
                            
                            # 构建更新后的代码块
                            updated_block = match[0] + updated_content
                            
                            # 替换原始内容中的代码块
                            content = content.replace(original_block, updated_block)
                        
                        # 写回文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                            
                        print(f"成功更新文件: {file_path}")
                        
                    except Exception as e:
                        print(f"处理文件 {file_path} 时出错: {str(e)}")


                if 0 < idx < len(lines) and voice_re.match(lines[idx - 1]):
                    lines[idx - 1] = voice_line
                    return lines, idx
                else:
                    lines.insert(idx, voice_line)
                    return lines, idx + 1  # 台词行下移一行

        def run_extract_to(base_dir, target_copy_name):
            # 运行一次extract，并把 base_dir/dialogue.tab 拷贝为 base_dir/target_copy_name
            language = persistent.extract_language
            args = ["dialogue", language]
            if getattr(persistent, "dialogue_format", None) == "txt":
                # 强制使用tab，忽略txt
                pass
            if getattr(persistent, "dialogue_strings", False):
                args.append("--strings")
            if getattr(persistent, "dialogue_notags", False):
                args.append("--notags")
            if getattr(persistent, "dialogue_escape", False):
                args.append("--escape")

            interface.processing(_("Ren'Py is extracting dialogue...."))
            project.current.launch(args, wait=True)
            project.current.update_dump(force=True)

            # 复制dialogue.tab为target_copy_name
            src = os.path.join(base_dir, "dialogue.tab")
            dst = os.path.join(base_dir, target_copy_name)
            if not os.path.exists(src):
                # 有些版本可能输出到其他名字，这里简单报错
                raise Exception("dialogue.tab not found after extract.")
            shutil.copyfile(src, dst)
            return dst


        def update_tl_block_for_id_change(old_id, new_id, new_character, new_dialogue):
            # 正则表达式模式，用于匹配translate代码块
            pattern = re.compile(r'^(translate\s+\w+\s+' + re.escape(old_id) + r':)(.*?)(?=^translate|\Z)', re.MULTILINE | re.DOTALL)

            for file_path in tl_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 查找所有匹配的代码块
                    matches = pattern.findall(content)
                    
                    if not matches:
                        continue
                            
                    # 对每个匹配的代码块进行处理
                    for match in matches:
                        original_block = match[0] + match[1]
                        
                        # 1. 删除所有注释行
                        lines = match[1].split('\n')
                        non_comment_lines = []
                        for line in lines:
                            # 保留非注释行（行首为#的整行注释去除）
                            if not line.strip().startswith('#'):
                                non_comment_lines.append(line)
                        
                        # 2. 添加新的注释
                        # 计算当前翻译待更新计数
                        count_match = re.search(r'#翻译待更新(?: x(\d+))?', match[1])
                        count = 1
                        if count_match and count_match.group(1):
                            count = int(count_match.group(1)) + 1
                        if new_character != "":
                            new_story = new_character + ":" + new_dialogue
                        else:
                            new_story = new_dialogue
                        # 构建新的注释
                        new_comments = "    #翻译待更新 x{}\n    #{}".format(count, new_story.replace('\n', '\n    # '))
                        
                        # 重新构建代码块，保留缩进
                        cleaned_block = '\n'.join(non_comment_lines)
                        
                        # 构建更新后的代码块 - 改进拼接逻辑，避免多余空行
                        updated_block_parts = [
                            match[0].replace(old_id, new_id),
                            new_comments
                        ]
                        
                        if voice_line_to_add:
                            updated_block_parts.append(voice_line_to_add)
                        
                        updated_block_parts.append(cleaned_block)
                        
                        # 使用换行符连接所有部分，但过滤掉空字符串
                        updated_block = "\n".join(part for part in updated_block_parts if part)
                        
                        # 替换原始内容中的代码块
                        content = content.replace(original_block, updated_block)
                    
                    # 写回文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                            
                    print(f"成功更新文件: {file_path}")
                    
                except Exception as e:
                    print(f"处理文件 {file_path} 时出错: {str(e)}")

        # 使用示例
        # tl_files = ["file1.rpy", "file2.rpy"]  # 需要替换为实际的文件列表
        # update_translation_voice("start_8162b3b9", "test5", tl_files)
        #辅助：是否包含中文
        def contains_cjk(s):
            return True if re.search(r'[\u4E00-\u9FFF]', s or '') else False

        #辅助：获取行尾换行
        def line_ending(s):
            m = re.search(r'(\r\n|\n|\r)$', s)
            return m.group(1) if m else ''
        
        def clear_screen_variables():
            # 清空文件选择屏幕的变量
            if hasattr(store, 'selected_file'):
                del store.selected_file
            if hasattr(store, 'update_text'):
                del store.update_text
            if hasattr(store, 'insert_voice'):
                del store.insert_voice
            if hasattr(store, 'update_identifier'):
                del store.update_identifier
            if hasattr(store, 'update_translation'):
                del store.update_translation
            
            # 清空其他可能的临时变量
            if hasattr(store, 'ops_by_file'):
                del store.ops_by_file
            if hasattr(store, 'modified_targets'):
                del store.modified_targets
            if hasattr(store, 'failed_ops'):
                del store.failed_ops
            if hasattr(store, 'tl_files'):
                del store.tl_files
        
            # 强制Ren'Py重新初始化屏幕变量
            renpy.restart_interaction()
        
        # 校验当前项目
        if project.current is None:
            interface.error(_("No project selected."), _("Please select a project first."))
            renpy.jump("front_page")

        # 通过文件选择屏幕获取：旧tab路径 + 选项
        # 返回 dict: { file: <path or None>, update_text: bool, insert_voice: bool, update_identifier: bool, update_translation: bool }
        ret = renpy.invoke_in_new_context(renpy.call_screen, "_file_picker", _("Select dialogue tab file "))
        if not ret or not ret.get("file"):
            renpy.jump("front_page")

        tab_file = ret["file"]
        opt_update_text = bool(ret.get("update_text"))
        opt_insert_voice = bool(ret.get("insert_voice"))
        opt_update_identifier = bool(ret.get("update_identifier"))
        opt_update_translation = bool(ret.get("update_translation"))

        base_dir = project.current.path
        game_dir = os.path.join(base_dir, "game")
        tl_language = persistent.extract_language or "None"

        # 读旧tab
        try:
            old_headers, old_rows, old_enc = parse_tab_file(tab_file)
        except Exception as e:
            interface.error(_("Failed to read tab file."), str(e))
            renpy.jump("front_page")

        # 必要列检查
        required_cols = ["identifier", "filename", "character", "dialogue", "line number"]
        try:
            ensure_required_columns([h.lower() for h in old_headers], required_cols)
        except Exception as e:
            interface.error(_("Invalid tab file format"), str(e))
            renpy.jump("front_page")

        # 第一步：extract为dialogue_newest.tab
        try:
            newest_tab_path = run_extract_to(base_dir, "dialogue_newest.tab")
        except Exception as e:
            interface.error(_("Failed to extract newest dialogue."), str(e))
            renpy.jump("front_page")

        # 读 newest
        try:
            new_headers, new_rows, new_enc = parse_tab_file(newest_tab_path)
        except Exception as e:
            interface.error(_("Failed to read newest tab."), str(e))
            renpy.jump("front_page")
        new_by_id = { (r.get("identifier") or ""): r for r in new_rows }

        # 建立映射
        # old_id -> old_row
        old_by_id = {}
        for r in old_rows:
            old_by_id[r["identifier"]] = r

        # new_id -> (filename, line), 以及 (filename,line)->new_id
        new_id_to_pos = {}
        new_pos_to_id = {}
        for r in new_rows:
            fn = r.get("filename", "")
            ln = as_int(r.get("line number"), None)
            if ln is None:
                continue
            new_id_to_pos[r.get("identifier", "")] = (fn, ln)
            new_pos_to_id[(fn, ln)] = r.get("identifier", "")

        # 收集需要修改的目标：仅处理在newest中能找到位置的旧ID
        ops_by_file = {}  # {abs_file_path: [ {line:int, old_id, char, dialogue, voice?}, ... ]}
        has_voice_col = "voice" in [h.lower() for h in old_headers]
        has_trans_col = "translation" in [h.lower() for h in old_headers]

        for oid, orow in old_by_id.items():
                if oid in new_id_to_pos:
                    # 新增：对比同一 Identifier 的 Character 与 Dialogue，若一致则跳过
                    nrow = new_by_id.get(oid)
                    if nrow is not None:
                        old_char = (orow.get("character") or "").strip()
                        old_dlg = (orow.get("dialogue") or "")
                        new_char = (nrow.get("character") or "").strip()
                        new_dlg = (nrow.get("dialogue") or "")
                        if has_voice_col:
                            old_voice = (orow.get("voice"or "")).strip()
                        if (old_char == new_char) and (old_dlg == new_dlg) and (opt_insert_voice== False  or old_voice == ""):
                            continue 
                    fn_rel, ln = new_id_to_pos[oid]
                    if not fn_rel:
                        continue
                    abs_path = os.path.join(base_dir, fn_rel)
                    op = {
                        "old_id": oid,
                        "filename_rel": fn_rel,
                        "line": ln,
                        "character": orow.get("character", ""),
                        "dialogue": orow.get("dialogue", ""),
                    }
                    if has_voice_col:
                        op["voice"] = orow.get("voice", "").strip()
                    if opt_update_translation and has_trans_col:
                        op["translation"] = orow.get("translation", "")
                    ops_by_file.setdefault(abs_path, []).append(op)


        # 按文件修改
        modified_targets = []  # 记录已修改的 (filename_rel, original_line, final_line_after_ops)
        failed_ops = []

        if opt_update_text or opt_insert_voice or opt_update_translation:
            interface.processing(_("Applying updates to scripts..."))

        # 为"更新翻译"准备tl文件列表
        tl_base_dir = os.path.join(game_dir, "tl")
        tl_files = []
        if opt_update_translation and os.path.isdir(tl_base_dir):
            # 遍历tl目录下的所有语言文件夹
            for lang_folder in os.listdir(tl_base_dir):
                lang_dir = os.path.join(tl_base_dir, lang_folder)
                if os.path.isdir(lang_dir):
                    # 遍历每个语言文件夹中的所有rpy文件
                    for root, dirs, files in os.walk(lang_dir):
                        for f in files:
                            if f.lower().endswith(".rpy"):
                                tl_files.append(os.path.join(root, f))


        # 逐文件执行（注意插入会影响后续行号，故按行号降序处理）
        for abs_path, ops in ops_by_file.items():
            if not (opt_update_text or opt_insert_voice or opt_update_translation):
                continue
            # 读取脚本
            if not os.path.exists(abs_path):
                failed_ops.extend([(abs_path, op["line"], "File not found") for op in ops])
                continue
            try:
                text, enc = read_text_file_guess_encoding(abs_path)
                lines = text.splitlines(True)  # 保留换行
            except Exception as e:
                failed_ops.extend([(abs_path, op["line"], "Read error: " + str(e)) for op in ops])
                continue

            # 备份
            try:
                if not os.path.exists(abs_path + ".bak"):
                    shutil.copyfile(abs_path, abs_path + ".bak")
            except:
                pass

            # 按行号降序
            ops_sorted = sorted(ops, key=lambda o: o["line"], reverse=True)

            for op in ops_sorted:
                idx = op["line"] - 1
                if idx < 0 or idx >= len(lines):
                    failed_ops.append((abs_path, op["line"], "Line out of range"))
                    continue

                original_idx = idx
                line = lines[idx]

                # 更新文本
                if opt_update_text:
                    newest_row = None
                    for nr in new_rows:
                        if nr.get("identifier") == op["old_id"]:
                            newest_row = nr
                            break
                    tl_id = (op.get("old_id") or op.get("identifier") or "").strip()
                    old_char = (op.get("character") or "").strip()
                    old_dlg = (op.get("dialogue") or "")
                    indent_match = re.match(r'^(\s*)', line)
                    indent = indent_match.group(1) if indent_match else ''
                    nl = line_ending(line)

                    if old_char == "":
                        # 仅替换第一处字符串（Dialogue）
                        new_line, q, s, e = replace_first_string_literal(line, old_dlg)
                        if new_line is None:
                            # 找不到字符串，回退为仅输出对白行
                            dlg = '"' + escape_renpy_string(old_dlg, '"') + '"'
                            lines[idx] = f'{indent}{dlg}{nl}'
                        else:
                            lines[idx] = new_line
                    else:
                        # 有角色
                        dlg = '"' + escape_renpy_string(old_dlg, '"') + '"'
                        if contains_cjk(old_char):
                            # "Character" Dialogue
                            who = '"' + escape_renpy_string(old_char, '"') + '"'
                            lines[idx] = f'{indent}{who} {dlg}{nl}'
                        else:
                            # Character Dialogue
                            who = old_char
                            lines[idx] = f'{indent}{who} {dlg}{nl}'

                    # 插入/替换语音
                    if opt_insert_voice:
                        voice_val = (op.get("voice") or "").strip() if has_voice_col else ""
                        if voice_val:
                            lines, idx_after = insert_or_replace_voice(lines, idx, tl_id,voice_val)
                            # 此时台词行的位置可能变化
                            idx = idx_after

                    modified_targets.append((op["filename_rel"], original_idx + 1, idx + 1))

            # 回写脚本
            try:
                write_text_file(abs_path, ''.join(lines), enc)
            except Exception as e:
                failed_ops.extend([(abs_path, -1, "Write error: " + str(e))])


        # 如需更新Identifier
        if opt_update_identifier:
            interface.processing(_("Re-extracting dialogue to update identifiers..."))
            try:
                changed_tab_path = run_extract_to(base_dir, "dialogue_identifier_changed.tab")
            except Exception as e:
                interface.error(_("Failed to extract after changes."), str(e))
                renpy.jump("front_page")

            # 读changed
            try:
                ch_headers, ch_rows, ch_enc = parse_tab_file(changed_tab_path)
            except Exception as e:
                interface.error(_("Failed to read changed tab."), str(e))
                renpy.jump("front_page")

            ch_pos_to_id = {}
            for r in ch_rows:
                fn = r.get("filename", "")
                ln = as_int(r.get("line number"), None)
                if ln is None:
                    continue
                ch_pos_to_id[(fn, ln)] = r.get("identifier", "")

            # 构造 newest 的 (fn, ln) -> old_id 映射（只对我们处理过的目标）
            newest_pos_to_oldid = {}
            for fn_rel, ln0, _ln1 in modified_targets:
                # 找出该位置在newest中的old_id（第二步拿到的就是newest的位置信息）
                oid = new_pos_to_id.get((fn_rel, ln0))
                if oid:
                    newest_pos_to_oldid[(fn_rel, ln0)] = oid

            # 为每个目标位置找到 changed 中的新identifier
            # 若插入语音导致行号+1，则先尝试原行号，再尝试+1；再不行尝试邻近范围
            updated_ids = {}  # old_id -> new_id
            for (fn_rel, ln0), oid in newest_pos_to_oldid.items():
                candidates = []
                # 首先 exact
                cand1 = ch_pos_to_id.get((fn_rel, ln0))
                if cand1:
                    candidates.append(cand1)
                # 若有插入语音，尝试+1
                if opt_insert_voice:
                    cand2 = ch_pos_to_id.get((fn_rel, ln0 + 1))
                    if cand2:
                        candidates.append(cand2)
                # 邻近搜索
                if not candidates:
                    for delta in range(2, 6):
                        c1 = ch_pos_to_id.get((fn_rel, ln0 + delta))
                        if c1: candidates.append(c1); break
                        c2 = ch_pos_to_id.get((fn_rel, ln0 - delta))
                        if c2: candidates.append(c2); break

                if candidates:
                    updated_ids[oid] = candidates[0]
            if updated_ids and opt_update_translation and tl_base_dir and os.path.isdir(tl_base_dir) and tl_files:
                # 从旧 tab 中取旧 id 对应的 Dialogue 文本（若无 Dialogue，则回退到 translation 列）
                lower_map = {h.lower(): h for h in old_headers}
                id_col = lower_map.get("identifier", "identifier")
                ch_col = lower_map.get("character")
                dlg_col = lower_map.get("dialogue")
                trans_col = lower_map.get("translation")
                voice_col = lower_map.get("voice")

                # 预构建旧 id -> (Character, Dialogue/Translation) 映射
                old_id_to_text = {}
                for r in old_rows:
                    oid = r.get(id_col, "").strip()
                    if not oid:
                        continue
                    ch = (r.get(ch_col) or "").strip() if ch_col else ""
                    dlg = (r.get(dlg_col) or "").strip() if dlg_col else ""
                    if (not dlg) and trans_col:
                        dlg = (r.get(trans_col) or "").strip()
                    old_id_to_text[oid] = (ch, dlg)
                    #voice = str(r.get(voice_col) or "").strip() if voice_col else ""
                    #old_id_to_text[oid] = (ch, dlg, voice)

                interface.processing(_("Updating TL blocks for identifier changes..."))
                for oid, nid in updated_ids.items():
                    if not oid or not nid or oid == nid:
                        continue
                    _ch, _dlg = old_id_to_text.get(oid, ("", ""))
                    #_ch, _dlg,_voice = old_id_to_text.get(oid, ("", "",""))
                    # 即便没有对白，也执行头部改名与插入提示
                    update_tl_block_for_id_change(oid, nid, _ch or "",_dlg or "")
                    #update_tl_block_for_id_change(oid, nid, _ch or "",_dlg or "", _voice or "")



            # 将updated_ids写回旧tab的Identifier列
            if updated_ids:
                # 用旧tab原列顺序输出
                lower_map = {h.lower(): h for h in old_headers}  # 保持原列大小写
                id_col = lower_map.get("identifier", "identifier")
                for r in old_rows:
                    oid = r.get(id_col, "")
                    if oid in updated_ids:
                        r[id_col] = updated_ids[oid]
                try:
                    save_tab_file(tab_file, old_headers, old_rows, old_enc)
                except Exception as e:
                    interface.error(_("Failed to write updated tab (identifiers)."), str(e))
                    renpy.jump("front_page")

            # 删除两个临时tab
            try:
                os.remove(changed_tab_path)
            except:
                pass
            try:
                os.remove(newest_tab_path)
            except:
                pass
        else:
            # 未勾选更新Identifier，也删除第一步产生的临时文件
            try:
                os.remove(newest_tab_path)
            except:
                pass
        
        if failed_ops:
            # 汇总警告
            msg = "Some updates could not be applied:\n"
            for (p, lno, why) in failed_ops[:20]:
                msg += f"- {p}:{lno} -> {why}\n"
            if len(failed_ops) > 20:
                msg += f"... and {len(failed_ops) - 20} more.\n"
            interface.info(msg)
        else:
            clear_screen_variables()
            interface.info(_("Done."))
    
    jump front_page
# 更新后的文件选择屏幕


label choose_tab_directory:
    python hide:
        interface.interaction(
            _("TAB FILE DIRECTORY"), 
            _("Please choose the directory containing tab files using the directory chooser.\n{b}The directory chooser may have opened behind this window.{/b}"), 
            _("This launcher will look for .tab files in this directory.")
        )

        # 使用Ren'Py的目录选择器
        path = choose_directory(persistent.tab_directory)
        
        if path:
            persistent.tab_directory = path[0]
            message = _("Ren'Py has set the tab file directory to:") + "\n" + repr(path[0])
            interface.info(message)

    return
screen _file_picker(title, pattern="*.tab", multiple=False):
    modal True
    
    default selected_file = None
    default update_text = True
    default insert_voice = True
    default update_identifier = False
    default update_translation = False
    
    frame:
        style_group "l"
        style "l_root"
        
        window:
            has vbox
            
            label "[title!q]"
            
            add HALF_SPACER
            
            frame:
                style "l_indent"
                xfill True
                
                has vbox
                
                add SEPARATOR2
                
                # 当前目录显示
                frame:
                    style "l_indent"
                    has vbox
                    hbox:
                        text _("Current Directory:")
                        textbutton _("Change Directory") action Call("choose_tab_directory")
                    add HALF_SPACER
                    
                    frame:
                        style "l_indent"
                        has vbox
                        
                        $ display_dir = persistent.tab_directory or (project.current.path if project.current else config.basedir)
                        text "[display_dir!q]" style "l_small_text"
                
                add SPACER
                add SEPARATOR2
                
                # 文件选择区域
                frame:
                    style "l_indent"
                    has vbox
                    
                    text _("Select File:")
                    
                    add HALF_SPACER
                    
                    frame:
                        style "l_indent"
                        xfill True
                        ymaximum 200
                        
                        vbox:
                            # 列出所有.tab文件
                            $ base_dir = persistent.tab_directory or (project.current.path if project.current else config.basedir)
                            $ files = []
                            
                            python:
                                import os
                                if os.path.exists(base_dir):
                                    for fn in os.listdir(base_dir):
                                        if fn.lower().endswith('.tab'):
                                            full_path = os.path.join(base_dir, fn)
                                            if os.path.isfile(full_path):
                                                files.append(fn)
                            
                            if files:
                                for fn in sorted(files):
                                    $ full_path = os.path.join(base_dir, fn)
                                    textbutton fn:
                                        action SetScreenVariable("selected_file", full_path)
                                        style "l_checkbox"
                                        selected (selected_file == full_path)
                            else:
                                text _("No .tab files found in this directory.") style "l_small_text"
                
                add SPACER
                add SEPARATOR2
                
                # 处理选项区域
                frame:
                    style "l_indent"
                    has vbox
                    
                    text _("Processing Options:")
                    
                    add HALF_SPACER
                    
                    frame:
                        style "l_indent"
                        has vbox
                        
                        textbutton _("Update text content") action ToggleScreenVariable("update_text") style "l_checkbox"
                        textbutton _("Insert voice code markers") action ToggleScreenVariable("insert_voice") style "l_checkbox"
                        textbutton _("Update dialogue identifiers") action ToggleScreenVariable("update_identifier") style "l_checkbox"
                        if update_identifier:
                            textbutton _("Update translation strings") action ToggleScreenVariable("update_translation") style "l_checkbox"

                add SPACER
                add SEPARATOR2
                
                # 选中文件显示
                if selected_file:
                    frame:
                        style "l_indent"
                        has vbox
                        
                        text _("Selected File:")
                        
                        add HALF_SPACER
                        
                        frame:
                            style "l_indent"
                            has vbox
                            
                            $ filename = os.path.basename(selected_file) if selected_file else ""
                            text "[filename!q]" style "l_small_text"
    
    # 底部按钮
    textbutton _("Process File") action [SensitiveIf(selected_file),Return({
                    "file": selected_file,
                    "update_text": update_text,
                    "insert_voice": insert_voice,
                    "update_identifier": update_identifier,
                    "update_translation": update_translation,
                })] style "l_left_button"
    textbutton _("Cancel") action Jump("front_page") style "l_right_button"