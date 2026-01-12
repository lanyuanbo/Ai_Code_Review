## Code Review 客户端

简洁的 Python 工具，支持输入自定义提示词并选择两个 git 分支进行 Code Review。

### 运行
在仓库根目录执行：

```bash
python code_review_client.py
```

按照交互提示选择起始与目标分支，输入提示词即可生成 review。

### 非交互使用示例
```bash
python code_review_client.py --from main --to feature --prompt "关注安全与性能" --output review.txt
```

参数说明：
- `--from` / `--to`：指定起始与目标分支名称。
- `--prompt`：直接传入自定义提示词（可替代交互输入）。
- `--prompt-file`：从文件读取提示词内容。
- `--output`：将生成的 review 文本写入文件。
