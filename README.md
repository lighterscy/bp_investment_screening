# BP Investment Screening

一个可迁移的轻量投研初筛工程骨架。

目标：输入项目 BP（PPT/PDF），在较短时间和较小成本下完成企业与行业基础研究、投资优势/劣势判断、跟进建议，并输出规范化 Word 投资研判文档。

本目录刻意不依赖上层 MarketResearch 工程代码。迁移时可直接复制整个 `bp_investment_screening/` 文件夹到新仓库。

## Design Principles

- BP 是项目方主张，不默认等于事实。
- 公司基础事实优先从 BP 抽取，外部搜索用于校验。
- 行业、市场、竞争、技术、政策等判断优先使用外部证据，BP 信息只作为补充。
- Layer1 保留基础研究层，但做轻量化主题展开。
- Layer2 不做复杂图迭代，使用投资初筛 skill 对 Layer1 结果做综合判断。
- 报告输出使用结构化 JSON 到 Word 模板渲染，不让 LLM 直接生成 docx。

## Target Pipeline

```text
BP file
  -> DocumentParser
  -> BPClaimExtractor
  -> Layer1Researcher
       - company topics
       - industry topics
       - BP claims + external evidence
  -> InvestmentAnalyzer
       - strengths
       - weaknesses
       - risks
       - follow-up recommendation
  -> ReportWriter
       - Markdown preview
       - Word docx from template
```

## Evidence Priority

| Topic Type | Preferred Source | Notes |
| --- | --- | --- |
| 公司名称、产品形态、团队履历 | BP first | 作为项目方披露信息，标注是否外部核验 |
| 核心技术与技术壁垒 | Balanced | BP 技术主张用于识别技术门类，外部资料用于校验技术路线、成熟度和壁垒 |
| 当前收入、订单、客户案例、试点数据 | BP first + verification required | 默认视为 claim，需后续 DD 验证 |
| 行业阶段、市场规模、竞争格局、政策环境 | External first | BP 信息容易乐观化，只做补充 |
| 商业模式、商业化进展、竞争优势 | Balanced | 需要对 BP 叙事做外部事实校验 |

## Layer1 Topics

当前 Layer1 topic 尽量减少相互交叠：

```text
公司基本信息
产品与服务
核心技术与技术壁垒
商业模式与商业化进展
团队与资源匹配度
行业阶段与市场空间
竞争格局与替代方案
政策环境与监管约束
```

## Directory Layout

```text
bp_investment_screening/
  pyproject.toml
  .env.example
  README.md
  data/
    case_name/
      inputs/
      outputs/
  prompts/
  skills/
  templates/
  src/bp_investment_screening/
  tests/
```

## Current Status

当前已经具备可本地运行的轻量闭环：

- 支持 TXT/Markdown 解析。
- 支持 PDF/PPTX 解析接口；安装 `.[docs]` 后可使用 `pymupdf` 和 `python-pptx`。
- 支持规则版 BP claims 初抽取，作为 LLM 抽取接入前的保守 baseline。
- 支持 Layer1/Layer2 占位综合判断。
- 支持 JSON/Markdown 报告输出，并生成机关公文风格的 `project_research_memo.docx`；如存在 docxtpl 模板，可额外渲染模板 Word。
- 支持 CLI 运行。

尚未实现真实 LLM 调用、联网搜索和正式投研判断生成。

## CLI Usage

```bash
PYTHONPATH=src python3 -m bp_investment_screening run path/to/bp.pdf --output data/outputs/demo
```

推荐按单项目组织数据：

```text
data/
  case1/
    inputs/
      project_bp.pdf
    outputs/
```

当输入文件位于 `inputs/` 目录下时，可以省略 `--output`，CLI 会默认写入同级 `outputs/`：

```bash
PYTHONPATH=src python3 -m bp_investment_screening run data/case1/inputs/project_bp.pdf
```

最终 Word 研究文档格式见 `templates/final_research_memo_format.md`。其中“技术背景”子标题只基于 Layer1 的“核心技术与技术壁垒”节点动态生成：配置 LLM 时优先调用 LLM，未配置时使用保守规则 fallback。LLM 的目标是为零基础读者搭建循序渐进的学习路径，先解释上位技术体系，再说明发展阶段、传统方案痛点，最后引出项目技术路线。

如果需要 PDF/PPTX/Word 支持，先安装可选依赖：

```bash
python3 -m pip install -e '.[docs]'
```

## Next Development Plan

1. 实现 LLM BP claim extraction：
   - 从页级文本中抽取公司、产品、团队、融资、收入、客户、市场等 claims
   - 保留 source page 与 needs_verification
2. 实现联网搜索：
   - 每个外部优先 topic 控制 1-2 个 query
   - 保存 evidence source、snippet、url、confidence
3. 实现正式轻量 Layer1 synthesis：
   - company: 基本信息、产品服务、核心技术与技术壁垒、商业化、团队
   - industry: 行业阶段、市场规模、竞争格局、政策监管
4. 实现 Layer2 投资初筛：
   - 使用 `skills/investment_screening.md`
   - 输出结构化 recommendation JSON
5. 完善 Word 输出：
   - 使用 `docxtpl`
   - 模板放在 `templates/investment_memo.docx`
6. 增加 tracer：
   - console + file/jsonl
   - 记录 BP 解析、Layer1 topic、搜索 query、Layer2 判断、报告路径
