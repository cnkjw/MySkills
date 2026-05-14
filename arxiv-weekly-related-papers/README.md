# arXiv Weekly Related Papers Skill 使用说明

这个 skill 用于围绕给定 arXiv 种子论文，抓取最近一周内相关领域的 arXiv 候选论文，并生成供 Codex、Claude Code、opencode 等代码助手阅读的分析包。脚本本身只调用 arXiv API，不调用任何 LLM API，也不需要 OpenAI、Anthropic 等 API key。

后续的相关度判断、推荐程度判断和拓展研究思路，应由正在执行该 skill 的 AI 助手基于分析包中的标题、摘要、分类和元数据完成。

## 基本流程

1. 准备一个或多个种子 arXiv ID。
2. 运行脚本抓取 arXiv 元数据并生成分析包。
3. 让当前 AI 助手读取分析包，评估候选论文相关性与推荐程度。
4. 输出最终 Markdown 文献报告。

## 快速开始

在 skill 目录下运行：

```bash
python3 scripts/fetch_related_arxiv.py \
  --ids 2305.00015,2405.06789 \
  --packet-output arxiv_packet.md \
  --json-output arxiv_packet.json
```

默认行为：

- 查询最近 7 个 UTC 日内更新的论文。
- 使用 `lastUpdatedDate`，因此会包含新版更新和新提交。
- 关注分类为 `hep-ex,nucl-ex,hep-ph,nucl-th`。
- 生成 Markdown 分析包；如果传入 `--json-output`，同时生成 JSON 包。

## 配置文件

脚本支持 JSON 配置文件，便于分发和复用。

如果没有显式传入 `--config`，脚本会自动依次查找：

1. `~/.arxiv-weekly-related-papers/config.json`
2. `~/.arxiv-weekly-related-papers/arxiv_weekly_config.json`

示例：

```json
{
  "categories": ["hep-ex", "nucl-ex", "hep-ph", "nucl-th"],
  "exclude_categories": ["astro-ph.CO", "gr-qc"]
}
```

也可以使用这些等价键：

- 关注分类：`categories`、`focus_categories`、`include_categories`
- 排除分类：`exclude_categories`、`excluded_categories`

命令行参数优先级高于配置文件。例如：

```bash
python3 scripts/fetch_related_arxiv.py \
  --ids 2305.00015 \
  --categories hep-ex,nucl-ex \
  --exclude-categories astro-ph.CO,gr-qc
```

## 排除分类

`--exclude-categories` 或配置文件里的 `exclude_categories` 用于节省后续 AI 分析 token。

规则是：如果一篇候选论文的任意 arXiv category 命中排除列表，该论文会在生成分析包前被直接移除。被排除论文的摘要不会写入 Markdown/JSON 包；分析包只记录排除数量和命中的排除分类统计。

例子：

```bash
python3 scripts/fetch_related_arxiv.py \
  --ids 2305.00015 \
  --categories hep-ex,nucl-ex,hep-ph,nucl-th \
  --exclude-categories astro-ph.CO,gr-qc \
  --packet-output arxiv_packet.md
```

## 常用参数

- `--ids`：必填，种子 arXiv ID，支持逗号或空格分隔。
- `--config`：可选 JSON 配置文件路径。
- `--packet-output`：Markdown 分析包输出路径。
- `--json-output`：可选 JSON 分析包输出路径。
- `--days`：向前回溯的 UTC 天数，默认 `7`。
- `--start-date` / `--end-date`：显式 UTC 日期范围，格式 `YYYY-MM-DD`。
- `--categories`：关注分类，覆盖配置文件。
- `--exclude-categories`：排除分类，覆盖配置文件。
- `--date-field`：`lastUpdatedDate` 或 `submittedDate`，默认 `lastUpdatedDate`。
- `--max-candidates`：最多抓取的候选论文数，默认 `1000`。
- `--page-size`：arXiv API 分页大小。
- `--batch-size`：Markdown 分析包中每批候选论文数量，默认 `20`。
- `--language`：分析包说明语言，`zh` 或 `en`，默认 `zh`。

## 日期字段选择

默认使用：

```bash
--date-field lastUpdatedDate
```

这会按 arXiv 的最近更新时间排序，并用返回的 `<updated>` 日期在本地过滤时间窗口，适合周报监控。

如果只想看首次提交的论文，使用：

```bash
--date-field submittedDate
```

## AI 分析要求

生成分析包后，执行该 skill 的 AI 助手应对每篇候选论文给出：

- `relevance_score`：0-100，和种子论文的主题或方法相关程度。
- `recommendation_score`：0-100，推荐研究组阅读或跟踪的程度。
- `relation_type`：`direct`、`method`、`background`、`contrast`、`weak`、`not_related`。
- `relevance_reason`：基于摘要和元数据的相关性说明。
- `recommendation_reason`：推荐或不推荐跟踪的理由。
- `research_ideas`：可拓展研究思路，或与当前研究结合的切入点。

不要使用本地关键词、作者、分类重合度作为最终相关性打分。脚本只负责收集和过滤候选论文；判断应由当前 AI 助手完成。

## 输出报告建议

最终 Markdown 报告固定采用下面这种结构，除非用户明确要求其他格式：

1. `# arXiv 周报：<种子数量或核心主题>相关候选分析`
2. `## 查询参数`
   - 固定使用下面的字段顺序和标签样式，但具体值必须从 skill 生成的 `arxiv_packet.md` 或 `arxiv_packet.json` 动态填充，不要照抄示例值：

     ```markdown
     - **生成时间**：<generated time>
     - **日期范围**：<start date> 至 <end date>（UTC，含端点）
     - **日期字段**：<date_field>
     - **关注类别**：<focus_categories>
     - **排除类别**：<exclude_categories 或 无>
     - **候选论文总数**：<candidate paper count>
     - **AI 分析前排除**：<excluded candidate count>
     ```

   - 标签保持中文，加粗，并使用中文全角冒号 `：`。
3. `## 种子论文概览`
   - 先用一小段总结共同研究主题。
   - 多篇种子论文时，按 2-4 个子方向分组。
   - 使用表格列出 `arXiv ID`、`核心内容`、`方法`。
4. `## AI 精选论文`
   - 按 `direct`、`method`、`background`、`weak` 的顺序分组。
   - 每篇论文使用编号标题，包含 arXiv 链接和标题。
   - 固定使用下面的中文元信息 bullet 格式：

     ```markdown
     - **作者**：Isabella Danhoni, Nicki Mullins, Jorge Noronha
     - **类别**：hep-ph, hep-th, nucl-th
     - **发表/更新**：2026-05-12
     - **相关度评分**：94/100
     - **推荐度评分**：92/100
     - **关系类型**：direct
     ```

   - 不要使用 `Authors`、`Categories`、`Published/Updated`、`Relevance score` 等英文标签，也不要把多个元信息用分号写在同一行。
   - 使用 `相关理由`、`推荐理由`、`拓展研究思路` 三个小段组织分析。
   - 拓展研究思路使用项目符号，内容要具体、可执行。
5. `## 候选论文完整列表（精简版）`
   - 使用紧凑表格列出值得保留的候选论文。
   - 表格列建议为 `#`、`arXiv ID`、`标题（简）`、`类别`、`相关度`、`推荐度`、`关系`。
   - 不要把几百篇明显无关论文全部展开；用一句话概括剩余无显著关联候选。
6. `## 方法论注记`
   - 说明候选来自 arXiv API，相关性由当前 AI 助手基于标题、摘要、类别和元数据判断。
   - 明确说明这不是穷尽式引文检索。

## 注意事项

- 脚本需要访问 `export.arxiv.org`。
- arXiv API 可能短期限流；脚本对 HTTP 429/503 做了简单退避重试。
- 候选集不是穷尽的语义检索结果，只是按 arXiv 分类和日期窗口抓取后的候选论文。
- 如果分析包很大，让 AI 助手按 batch 分段分析，并保留中间评估表。
