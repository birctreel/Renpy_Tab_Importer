label import_dialogue:
    python:
        import os
        import re
        import io
        import shutil
        ########################################
        #提前定义去
        ########################################
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
            # 按原来的列顺序往外写
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

        def escape_renpy_string(s, quote_char='"'):
            #避免重复转义
            if '\\' in s:
                # 检查是否已经是正确转义的格式
                return s
            else:
                # 对未转义的字符串进行基本转义
                return s.replace('\\', '\\\\').replace(quote_char, '\\' + quote_char)
        #     # 别转了会出错
        #     s = s.replace('\\', '\\\\')
        #     if quote == '"':
        #         s = s.replace('"', '\\"')
        #     else:
        #         s = s.replace("'", "\\'")
        #     return s

        def replace_first_string_literal(line, new_text):
            # 找到一行里第一对引号里的字，把它换掉。支持 "..."" 和 '...'
            # 返回 (新行, 用到的引号, 起始位置, 结束位置)，找不到就全是 None
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

            # 往后找配对的引号，顺便处理转义
            i = qpos + 1
            escaped = False
            while i < len(line):
                c = line[i]
                if escaped:
                    escaped = False
                elif c == '\\':
                    escaped = True
                elif c == qchar:
                    # 找到收尾的引号了
                    start = qpos
                    end = i
                    new_content = escape_renpy_string(new_text, qchar)
                    new_line = line[:start+1] + new_content + line[end:]
                    return new_line, qchar, start, end
                i += 1

            # 没等到收尾引号
            return None, None, None, None

        def try_update_character_token(line, desired_char):
            # 把第一对引号前面的最后一个“词”换成 desired_char
            # 如果 desired_char 为空，就尽量把这个词删了
            m = re.match(r'^(\s*)(.*?)(["\'])', line)
            if not m:
                return line, False
            indent = m.group(1)
            before = m.group(2)
            quote = m.group(3)

            # 如果 before 是空的或全空白，当旁白用，不用换人
            if before.strip() == '':
                if desired_char:
                    # 这时候要补上角色名
                    return f'{indent}{desired_char} {quote}' + line[m.end():], True
                else:
                    return line, False

            # 有东西的话，就把最后一个非空白的当角色名
            tokens = re.split(r'(\s+)', before)
            idx = None
            for i in range(len(tokens)-1, -1, -1):
                if tokens[i].strip() != '':
                    idx = i
                    break
            if idx is None:
                if desired_char:
                    return f'{indent}{desired_char} {quote}' + line[m.end():], True
                else:
                    return line, False

            if not desired_char:
                # 把左边是空白的话顺手删了
                new_tokens = tokens[:]
                new_tokens[idx] = ''
                if idx-1 >= 0 and new_tokens[idx-1].strip() == '':
                    new_tokens[idx-1] = ''
                new_before = ''.join(new_tokens)
                return f'{indent}{new_before}{quote}' + line[m.end():], True
            else:
                tokens[idx] = desired_char
                # 角色名后面没空格的话，补一个
                if idx+1 >= len(tokens) or tokens[idx+1].strip() != '':
                    tokens.insert(idx+1, ' ')
                new_before = ''.join(tokens)
                return f'{indent}{new_before}{quote}' + line[m.end():], True

        def insert_or_replace_voice(lines, idx, old_id,voice_value):
            # 在第 idx 行台词前面插入或替换一行 voice "xxx"
            # 返回新的 lines，还有台词行的新位置（大概率变了
            if idx < 0 or idx >= len(lines):
                return lines, idx
            # 缩进
            m = re.match(r'^(\s*)', lines[idx])
            indent = m.group(1) if m else ''
            if voice_value != None and voice_value != "":
                voice_value = voice_value.strip()
                if voice_value.startswith('voice '):
                    voice_line = f'{indent}{voice_value.rstrip()}\n'
                else:
                    voice_line = f'{indent}voice "{voice_value}"\n'
                # 如果上一行已经有 voice，就直接替换；没有就插一行


                # 顺带把翻译文件里的 voice 也更新一下
                pattern = re.compile(r'^(translate\s+\w+\s+' + re.escape(old_id) + r':)(.*?)(?=^translate|\Z)', re.MULTILINE | re.DOTALL)
                
                for file_path in tl_files:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        matches = pattern.findall(content)
                        
                        if not matches:
                            continue
                            
                        # 每个块都处理一遍
                        for match in matches:
                            original_block = match[0] + match[1]
                            
                            # 检查voice
                            voice_pattern = re.compile(r'^\s*voice\s+".*?"', re.MULTILINE)
                            has_voice = voice_pattern.search(match[1])
                            
                            if has_voice:
                                # 有的话就把里面的值换掉
                                updated_content = voice_pattern.sub(f'    voice "{voice_value}"', match[1])
                            else:
                                # 没有就补一行 voice
                                lines = match[1].split('\n')
                                insert_pos = 0
                                for i, line in enumerate(lines):
                                    if line.strip() and not line.strip().startswith('#'):
                                        insert_pos = i
                                        break
                                lines.insert(insert_pos, f'    voice "{voice_value}"')
                                updated_content = '\n'.join(lines)
                            
                            # 拼好块
                            updated_block = match[0] + updated_content
                            
                            # 覆盖块
                            content = content.replace(original_block, updated_block)
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                            
                        print(f"成功更新文件: {file_path}")
                        
                    except Exception as e:
                        print(f"处理文件 {file_path} 时出错: {str(e)}")


                if 0 < idx < len(lines) and re.match(r'^\s*voice\s+', lines[idx - 1]):
                    lines[idx - 1] = voice_line
                    return lines, idx
                else:
                    lines.insert(idx, voice_line)
                    return lines, idx + 1  # 台词行被顶下去一行

        def run_extract_to(base_dir, target_copy_name):
            language = persistent.extract_language
            args = ["dialogue", language]
            #if getattr(persistent, "dialogue_format", None) == "txt":
            #    pass
            if getattr(persistent, "dialogue_strings", False):
                args.append("--strings")
            if getattr(persistent, "dialogue_notags", False):
                args.append("--notags")
            if getattr(persistent, "dialogue_escape", False):
                args.append("--escape")

            interface.processing(_("Ren'Py is extracting dialogue...."))
            project.current.launch(args, wait=True)
            project.current.update_dump(force=True)

            # 把 dialogue.tab 复制成 target_copy_name
            src = os.path.join(base_dir, "dialogue.tab")
            dst = os.path.join(base_dir, target_copy_name)
            if not os.path.exists(src):
                raise Exception("dialogue.tab not found after extract.")
            shutil.copyfile(src, dst)
            return dst


        def update_tl_block_for_id_change(old_id, new_id, new_character, new_dialogue):
            # 更新翻译（尤其是identifier
            pattern = re.compile(r'^(translate\s+\w+\s+' + re.escape(old_id) + r':)(.*?)(?=^translate|\Z)', re.MULTILINE | re.DOTALL)

            for file_path in tl_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    matches = pattern.findall(content)
                    
                    if not matches:
                        continue
                            
                    for match in matches:
                        original_block = match[0] + match[1]
                        
                        # 删除无用注释行
                        lines = match[1].split('\n')
                        non_comment_lines = []
                        for line in lines:
                            if not line.strip().startswith('#'):
                                non_comment_lines.append(line)
                        
                        # 2) 加上新的提示注释
                        # 算一下这条"翻译待更新"该加到第几次了
                        count_match = re.search(r'#翻译待更新(?: x(\d+))?', match[1])
                        count = 1
                        if count_match and count_match.group(1):
                            count = int(count_match.group(1)) + 1
                        if new_character != "":
                            new_story = new_character + ":" + new_dialogue
                        else:
                            new_story = new_dialogue
                        # 拼新的注释内容
                        new_comments = "    #翻译待更新 x{}\n    #{}".format(count, new_story.replace('\n', '\n    # '))
                        
                        # 重新拼一下块，缩进照旧
                        cleaned_block = '\n'.join(non_comment_lines)
                        
                        # 拼接更新后的代码块，去掉多余空行
                        updated_block_parts = [
                            match[0].replace(old_id, new_id).rstrip(),  # 去掉尾部空白
                            new_comments.rstrip()  # 去掉尾部空白
                        ]
                        
                        if cleaned_block.strip():  # 只有当cleaned_block有内容时才添加
                            updated_block_parts.append(cleaned_block.rstrip())
                        
                        # 用换行把各段合起来，避免多余空行
                        updated_block = "\n".join(part for part in updated_block_parts if part.strip())
                        
                        # 如果原块末尾有换行，保持相同的格式
                        if original_block.endswith('\n'):
                            updated_block += '\n'
                        
                        # 替换翻译块
                        content = content.replace(original_block, updated_block)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                            
                    print(f"成功更新文件: {file_path}")
                    
                except Exception as e:
                    print(f"处理文件 {file_path} 时出错: {str(e)}")


        def contains_cjk(s):
            return True if re.search(r'[\u4E00-\u9FFF]', s or '') else False

        # 小工具：拿到行尾的换行符
        def line_ending(s):
            m = re.search(r'(\r\n|\n|\r)$', s)
            return m.group(1) if m else ''
        
        # def clear_screen_variables():
        #     #怀疑可能是变量导致第二次运行时失败，清理下试试
        #     if hasattr(store, 'selected_file'):
        #         del store.selected_file
        #     if hasattr(store, 'update_text'):
        #         del store.update_text
        #     if hasattr(store, 'insert_voice'):
        #         del store.insert_voice
        #     if hasattr(store, 'update_identifier'):
        #         del store.update_identifier
        #     if hasattr(store, 'update_translation'):
        #         del store.update_translation
            
        #     if hasattr(store, 'ops_by_file'):
        #         del store.ops_by_file
        #     if hasattr(store, 'modified_targets'):
        #         del store.modified_targets
        #     if hasattr(store, 'failed_ops'):
        #         del store.failed_ops
        #     if hasattr(store, 'tl_files'):
        #         del store.tl_files
        
        #     renpy.restart_interaction()
        
        ########################################
        #调用页面区
        ########################################
        # 校验当前项目
        if project.current is None:
            interface.error(_("No project selected."), _("Please select a project first."))
            renpy.jump("front_page")

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
        #tl_language = persistent.extract_language or "None"

        
        ########################################
        #处理翻译文件（仅在tl文件夹里面寻找）
        ########################################
        # 为"更新翻译"准备tl文件列表
        tl_base_dir = os.path.join(game_dir, "tl")
        tl_files = []
        if opt_update_translation and os.path.isdir(tl_base_dir):
            for lang_folder in os.listdir(tl_base_dir):
                lang_dir = os.path.join(tl_base_dir, lang_folder)
                if os.path.isdir(lang_dir):
                    for root, dirs, files in os.walk(lang_dir):
                        for f in files:
                            if f.lower().endswith(".rpy"):
                                tl_files.append(os.path.join(root, f))


        ########################################
        #开始处）
        ########################################

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

        # 建立映射old_id -> old_row
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
                        else:
                            old_voice = ""
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

        ########################################
        #修改剧情文本
        ########################################


        modified_targets = []  # 记录已修改的 (filename_rel, original_line, final_line_after_ops)
        failed_ops = []

        if opt_update_text or opt_insert_voice or opt_update_translation:
            interface.processing(_("Applying updates to scripts..."))



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


        
        ########################################
        #更新Identifier
        ########################################

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

            # 构造 newest 的 (fn, ln) -> old_id 映射（只对处理过的目标
            newest_pos_to_oldid = {}
            for fn_rel, ln0, _ln1 in modified_targets:
                # 找出该位置在newest中的old_id（第二步拿到的就是newest的位置信息）
                oid = new_pos_to_id.get((fn_rel, ln0))
                if oid:
                    newest_pos_to_oldid[(fn_rel, ln0)] = oid

            # 为每个目标位置找到 changed 中的新identifier，如果行号+1，则先尝试原行号，再尝试+1；再不行尝试邻近范围
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
                for exoid, exnid in updated_ids.items():
                    if not exoid or not exnid or exoid == exnid:
                        continue
                    _ch, _dlg = old_id_to_text.get(exoid, ("", ""))
                    #_ch, _dlg,_voice = old_id_to_text.get(oid, ("", "",""))
                    # 即便没有对白，也执行头部改名与插入提示
                    update_tl_block_for_id_change(exoid, exnid, _ch or "",_dlg or "")
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
            #clear_screen_variables()
            interface.info(_("Done."))
    
    jump front_page


########################################
#选择tab文件页
########################################
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

########################################
#参考Preference页的完美UI！！（草
########################################

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